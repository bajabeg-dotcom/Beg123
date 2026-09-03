"""Factory-based optimizer using Gold DNA targets and GM-to-RX maps."""
from copy import deepcopy
from collections import Counter,defaultdict
import math
from statistics import mean, pstdev
from .midi import Event, note_rows
from .features import GoldDNAModel, extract_features
from .solo import choose_solo_model, solo_descriptor
from .strumming import STRUM_COMMANDS, STRING_COMMANDS, choose_strumming_model
from .sound_intelligence import (
    analyze_track_assignments, apply_midi_headroom, repair_regular_rhythm_guitars,
    factory_calibrated_velocity,soft_limit_velocity,
)
from .instrument_identity import canonical_identity,identities_compatible
from .instrument_structure import choose_factory_model,choose_identity_model

ROLES = ("melodic","bass","guitar","accompaniment","percussion","drums")

def _factory_instrument_velocity(original,proposed,role,position,factory_model,performance_model,strength):
    factory_profile=factory_model.profiles.get(role) or factory_model.profiles.get("melodic")
    performance_profile=(performance_model.profiles.get(role) or performance_model.profiles.get("melodic")) if performance_model else None
    if not factory_profile:return original
    factory_bin=factory_profile.velocity_by_16th[position];factory_stats=factory_bin if factory_bin.count else factory_profile.velocity
    if performance_profile:
        gold_bin=performance_profile.velocity_by_16th[position];gold_stats=gold_bin if gold_bin.count else performance_profile.velocity
        ratio=max(.25,min(2.0,factory_stats.std/max(1.0,gold_stats.std)))
        shaped=factory_stats.mean+(proposed-gold_stats.mean)*ratio
    else:shaped=factory_stats.mean+(proposed-original)*.5
    amount=max(0,min(1,float(strength)))
    return max(1,min(127,round(original*(1-amount)+shaped*amount)))

def _role(channel, program=None):
    fixed={8:"bass",9:"drums",10:"percussion",11:"accompaniment",12:"accompaniment",13:"accompaniment",14:"accompaniment",15:"accompaniment"}.get(channel)
    if fixed: return fixed
    if program is not None and 32 <= int(program) <= 39: return "bass"
    if program is not None and 24 <= int(program) <= 31: return "guitar"
    return "melodic"

def _protected_velocity(original, proposed, rx_name, role, note=None, rx_rules=None,audit=None):
    """Keep conversion from accidentally selecting an RX noise/articulation.

    Newly mapped bass and guitar parts stay in the normal playing oscillator.
    Drums retain ghost/accent intent by limiting how far Gold normalization can
    move a hit. Other sounds use the proposed Gold-derived velocity unchanged.
    """
    name=(rx_name or "").lower()
    audit=audit if audit is not None else Counter()
    strict=bool(rx_rules and "__report__" in rx_rules and rx_rules.get("__report__",{}).get("mode")=="strict")
    gate=(rx_rules or {}).get("__gate__",{}).get(rx_name,{})
    if rx_name and strict and not gate.get("transform_existing_allowed",False):
        audit["fail_closed_velocity_preserved"]+=int(proposed!=original)
        if gate.get("conflicted"):audit["conflict_velocity_preserved"]+=int(proposed!=original)
        return original
    rules=[rule for rule in (rx_rules or {}).get(rx_name,()) if rule.get("runtime_transform_allowed",not strict) and not rule.get("malformed")]
    matching=[rule for rule in rules if rule.get("velocity_min") is not None and rule.get("velocity_max") is not None
        and int(rule["velocity_min"])<=original<=int(rule["velocity_max"])
        and (note is None or rule.get("key_min") is None or int(rule["key_min"])<=note<=int(rule.get("key_max",127)))]
    if matching:
        rule=sorted(matching,key=lambda item:(int(item["velocity_max"])-int(item["velocity_min"]),item.get("oscillator",99)))[0]
        low,high=int(rule["velocity_min"]),int(rule["velocity_max"]); switch=rule.get("switch_value")
        if "slap" in name and switch and low < int(switch) <= high:
            if original>=int(switch): low=int(switch)
            else: high=int(switch)-1
        audit["evidence_zone_clamps"]+=int(proposed<low or proposed>high)
        return max(low,min(high,proposed))
    if strict and rx_name:
        audit["fail_closed_velocity_preserved"]+=int(proposed!=original);return original
    if "slap" in name and "bass rx" in name:
        # Keep the original side of the likely internal low/high switch 87.
        if original >= 114:
            return max(114,min(127,proposed))
        if original >= 87:
            return max(87,min(113,proposed))
        return max(53,min(86,proposed))
    if "guitar rx" in name:
        return max(53,min(93,proposed))
    if "bass rx" in name:
        return max(53,min(113,proposed))
    if role in ("drums","percussion"):
        return max(1,min(127,max(original-12,min(original+12,proposed))))
    return proposed

def _targets(stats):
    result={}
    for role in ROLES:
        selected=[r for r in stats if r["role"]==role and r["note_count"]]
        if selected:
            weight=sum(r["note_count"] for r in selected)
            result[role]={k:sum(float(r[k])*r["note_count"] for r in selected)/weight for k in ("velocity_mean","velocity_std","density_per_quarter")}
            result[role]["duration_quarters"]=sum(
                float(r.get("duration_quarters") if r.get("duration_quarters") is not None
                      else float(r["duration_mean"])/max(1,float(r.get("division",384))))*r["note_count"]
                for r in selected)/weight
    return result

def optimize(midi,gold_stats,mappings,strength=.7,preserve_sysex=False,gold_model:GoldDNAModel|None=None,
             rx_rules=None,solo_models=None,solo_strength=.65,solo_channels=None,
             strumming_models=None,strumming_strength=.7,strumming_humanize=.5,
             strumming_variation=True,style_section=None,capo=0,sound_intelligence=None,
             assign_unknown_sounds=True,mix_headroom=True,headroom_strength=.85,
             guitar_repair=True,guitar_repair_strength=.65,instrument_structure=None,
             rx_mapping_mode="strict"):
    strength=max(0.,min(1.,float(strength))); result=deepcopy(midi); targets=_targets(gold_stats); cv=cd=0
    tempo_bpm=None; meter_num=meter_den=4
    for events in result.tracks:
        for event in events:
            if event.kind=="meta" and event.data1==0x51 and len(event.raw)==3 and tempo_bpm is None:
                micros=int.from_bytes(event.raw,"big"); tempo_bpm=60_000_000/micros if micros else None
            elif event.kind=="meta" and event.data1==0x58 and len(event.raw)>=2:
                meter_num=int(event.raw[0]); meter_den=2**int(event.raw[1])
    sysex_quarantined=0
    if not preserve_sysex:
        for events in result.tracks:
            sysex_quarantined += sum(event.kind=="sysex" for event in events)
            events[:] = [event for event in events if event.kind!="sysex"]
    intelligence=sound_intelligence or {};assignments=analyze_track_assignments(result,intelligence) if intelligence else {}
    mix_profiles=intelligence.get("mix",{});factory_assigned=[];factory_assignment_keys=set();auto_sound_threshold=.75
    identity_rejections=[];identity_corrections={};factory_structure_choices={};identity_timelines={}
    mapping_evidence_rejections=[];unverified_mappings_applied=0
    evidence_policy=(rx_rules or {}).get("__policy__",{})
    strict_evidence=bool((rx_rules or {}).get("__report__",{}).get("mode")=="strict")
    rx_mapping_mode="catalog_review" if rx_mapping_mode=="catalog_review" else "strict"
    address_identities=defaultdict(set)
    for sound in intelligence.get("sounds",[]):
        address_identities[(int(sound["bank_msb"]),int(sound["bank_lsb"]),int(sound["program"]))].add(
            sound.get("identity") or canonical_identity(sound["program"],sound.get("name",""),sound.get("role","")))
    index={(int(x["source_bank_msb"]),int(x["source_bank_lsb"]),int(x["source_program"]),x["role"]):x for x in mappings}; mapped=0; unmapped=set(); timelines={}
    for track_index,events in enumerate(result.tracks):
        banks={c:[0,0] for c in range(16)}; additions=[]
        for event in sorted(events,key=lambda e:(e.tick,e.order)):
            ch=int(event.channel or 0)
            if event.kind=="control" and event.data1 in (0,32): banks[ch][0 if event.data1==0 else 1]=int(event.data2 or 0)
            elif event.kind=="program":
                source_program=int(event.data1 or 0); assignment=assignments.get((track_index,ch),{});role=assignment.get("role") or _role(ch,source_program)
                key=(*banks[ch],int(event.data1 or 0),role); target=index.get(key)
                if not target and role in ("bass","guitar","accompaniment"):
                    target=index.get((*banks[ch],int(event.data1 or 0),"melodic"))
                address=(key[0],key[1],source_program);known_ids=address_identities.get(address,set())
                if len(known_ids)==1:source_identity=next(iter(known_ids))
                elif assignment.get("source")=={"bank_msb":address[0],"bank_lsb":address[1],"program":address[2]}:source_identity=assignment.get("source_identity")
                else:source_identity=canonical_identity(source_program,"",role)
                identity_timelines.setdefault((track_index,ch),[]).append((event.tick,source_identity))
                if target:
                    same_address=(key[0],key[1],source_program)==(int(target["target_bank_msb"]),int(target["target_bank_lsb"]),int(target["target_program"]))
                    if not identities_compatible(source_program,source_identity.replace("_"," "),int(target["target_program"]),str(target.get("rx_name","")),role,same_address=same_address):
                        identity_rejections.append({"track":track_index,"channel":ch,"source_identity":source_identity,
                            "rejected_target":str(target.get("rx_name","")),"reason":"cross_instrument_identity"});target=None
                if target and strict_evidence:
                    sound_key=f"sound:{int(target['target_bank_msb'])}:{int(target['target_bank_lsb'])}:{int(target['target_program'])}:{str(target.get('rx_name',''))}"
                    sound_gate=evidence_policy.get("sounds",{}).get(sound_key,{})
                    evidence_allowed=bool(sound_gate.get("generate_articulation_allowed"))
                    if not evidence_allowed and rx_mapping_mode=="strict":
                        mapping_evidence_rejections.append({"track":track_index,"channel":ch,
                            "source":address,"target":str(target.get("rx_name","")),
                            "reason":"target_sound_not_confirmed_by_primary_evidence"})
                        target=None
                    elif not evidence_allowed:
                        unverified_mappings_applied+=1
                if target:
                    event.data1=int(target["target_program"]); rx_name=str(target.get("rx_name", "")); additions += [Event(event.tick,event.order-.2,"control",ch,0,int(target["target_bank_msb"]),0xB0|ch),Event(event.tick,event.order-.1,"control",ch,32,int(target["target_bank_lsb"]),0xB0|ch)]; mapped+=1
                elif (assign_unknown_sounds and (not strict_evidence or rx_mapping_mode=="catalog_review")
                      and assignment.get("source")=={"bank_msb":address[0],"bank_lsb":address[1],"program":address[2]}
                      and assignment.get("unknown_user_sound") and assignment.get("recommendation")
                      and float(assignment.get("sound_confidence",0))>=auto_sound_threshold):
                    recommendation=assignment["recommendation"];event.data1=int(recommendation["program"]);rx_name=""
                    additions += [Event(event.tick,event.order-.2,"control",ch,0,int(recommendation["bank_msb"]),0xB0|ch),
                        Event(event.tick,event.order-.1,"control",ch,32,int(recommendation["bank_lsb"]),0xB0|ch)]
                    audit_key=(track_index,ch,tuple(assignment["source"].values()),recommendation["bank_msb"],recommendation["bank_lsb"],recommendation["program"])
                    if audit_key not in factory_assignment_keys:
                        factory_assignment_keys.add(audit_key);factory_assigned.append({"track":track_index,"channel":ch,"role":role,"confidence":assignment["sound_confidence"],
                            "source":assignment["source"],"target":{key:recommendation[key] for key in ("name","bank_msb","bank_lsb","program")}})
                else: unmapped.add(f"MSB {key[0]} / LSB {key[1]} / Program {key[2]+1} / {role}")
                timelines.setdefault((track_index,ch),[]).append((event.tick,role,rx_name if target else "",source_program))
        events.extend(additions)
    def state_for(track,channel,tick):
        state=(_role(channel),"",0)
        for start,role,rx_name,program in timelines.get((track,channel),()):
            if start>tick: break
            state=(role,rx_name,program)
        return state
    def identity_for(track,channel,tick,program=0,role=""):
        identity=canonical_identity(program,"",role)
        for start,value in identity_timelines.get((track,channel),()):
            if start>tick:break
            identity=value
        return identity
    notes=note_rows(result)
    guitar_mode_tracks={}
    grouped_notes={}
    for row in notes: grouped_notes.setdefault((row["track"],row["channel"]),[]).append(row)
    for key,group in grouped_notes.items():
        role,_,source_program=state_for(key[0],key[1],min(row["start"] for row in group))
        commands=[row for row in group if row["note"] in STRUM_COMMANDS or row["note"] in STRING_COMMANDS]
        texts=" ".join(event.raw.decode("latin1","replace") for event in result.tracks[key[0]]
            if event.kind=="meta" and event.data1 in (1,3) and event.raw).lower()
        positive=("guitar","gtr","nylon","steel guitar","steel str","12 string","distort","jazz gt","clean gt","clean funk","funk stein","mandolin")
        negative=(" kit","kit ","drum","perc","piano","organ","bass","choir","sax","brass","synth","pad")
        named=any(token in texts for token in positive); explicitly_not_guitar=any(token in f" {texts} " for token in negative)
        has_instrument_text=any(event.kind=="meta" and event.data1==1 and event.raw for event in result.tracks[key[0]])
        evidence=named or (24<=source_program<=31 and not has_instrument_text) or (not has_instrument_text and not explicitly_not_guitar and len(commands)>=4 and len(commands)/max(1,len(group))>=.75)
        if role in ("accompaniment","guitar") and len(commands)>=2 and evidence:
            guitar_mode_tracks[key]={"role":role,"commands":len(commands),"notes":len(group)}
    protected=timing_changed=controller_changed=overlap_clamps=headroom_velocity_limited=factory_velocity_calibrated=0; role_reports={};rx_evidence_audit=Counter()
    for role in ROLES:
        selected=[r for r in notes if state_for(r["track"],r["channel"],r["start"])[0]==role
            and not ((r["track"],r["channel"]) in guitar_mode_tracks and (r["note"]<=47 or r["note"]>=96))]
        target=targets.get(role) or targets.get("melodic")
        if not selected: continue
        sm=mean(r["velocity"] for r in selected); ss=pstdev(r["velocity"] for r in selected) or 1
        input_duration_quarters=mean(r["duration"]/midi.division for r in selected); role_changed=0
        ratio=max(.67,min(1.5,target["duration_quarters"]/max(1/midi.division,input_duration_quarters))) if target else 1
        for row in selected:
            position=round((row["start"]/midi.division)*4)%16
            program=state_for(row["track"],row["channel"],row["start"])[2];identity=identity_for(row["track"],row["channel"],row["start"],program,role)
            cache_key=(identity,role)
            if cache_key not in identity_corrections:
                identity_corrections[cache_key]=choose_identity_model(instrument_structure or {},identity,role,tempo_bpm,meter_num,meter_den)
            identity_choice=identity_corrections[cache_key];active_model=identity_choice[0] if identity_choice else gold_model
            if active_model and (role in active_model.profiles or "melodic" in active_model.profiles):
                note_target=active_model.transform_note(role,position,row["velocity"],row["duration"]/midi.division,
                    source_velocity_mean=sm,source_velocity_std=ss,strength=strength)
                v=note_target.velocity
                grid_tick=round(row["start"]/(midi.division/4))*(midi.division/4)
                desired=round(grid_tick+note_target.timing_offset_quarters*midi.division)
                max_shift=max(1,round(.08*midi.division)); shift=max(-max_shift,min(max_shift,desired-row["start"]))
                shift=max(-row["start"],shift)
                if shift:
                    row["on_event"].tick+=shift; row["off_event"].tick+=shift; row["start"]+=shift; timing_changed+=1
                duration=max(1,round(note_target.duration_quarters*midi.division))
                duration=max(round(row["duration"]*.67),min(round(row["duration"]*1.5),duration))
            elif target:
                gold_v=target["velocity_mean"]+(row["velocity"]-sm)*target["velocity_std"]/ss
                v=max(1,min(127,round(row["velocity"]*(1-strength)+gold_v*strength)))
                duration=max(1,round(row["duration"]*((1-strength)+ratio*strength)))
            else:
                continue
            if cache_key not in factory_structure_choices:
                factory_structure_choices[cache_key]=choose_factory_model(instrument_structure or {},identity,role,meter_num,meter_den)
            factory_choice=factory_structure_choices[cache_key]
            calibrated=(_factory_instrument_velocity(row["velocity"],v,role,position,factory_choice[0],active_model,headroom_strength)
                if mix_headroom and factory_choice else factory_calibrated_velocity(row["velocity"],v,role,mix_profiles,headroom_strength)
                if mix_headroom and mix_profiles else v)
            factory_velocity_calibrated+=calibrated!=v;v=calibrated
            limited=soft_limit_velocity(v,role,mix_profiles) if mix_headroom and mix_profiles else v
            headroom_velocity_limited+=limited!=v;v=limited
            rx_name=state_for(row["track"],row["channel"],row["start"])[1]
            safe_v=_protected_velocity(row["velocity"],v,rx_name,role,row.get("note"),rx_rules,rx_evidence_audit)
            if safe_v!=v: protected+=1
            v=safe_v
            if v!=row["velocity"]: row["on_event"].data2=v; cv+=1; role_changed+=1
            if duration!=row["duration"]: row["off_event"].tick=row["start"]+duration; cd+=1
        role_reports[role]={"notes":len(selected),"velocity_changed":role_changed}
    # Gold reshapes only CC1/CC11 performance motion here.  The later Factory
    # headroom pass handles CC7/CC11 together so musical expression survives
    # without letting every track sit at the MIDI ceiling.
    if gold_model:
        for ti,events in enumerate(result.tracks):
            for event in events:
                if event.kind!="control" or event.data1 not in (1,11): continue
                if (ti,int(event.channel or 0)) in guitar_mode_tracks: continue
                role=state_for(ti,int(event.channel or 0),event.tick)[0]
                profile=gold_model.profiles.get(role) or gold_model.profiles.get("melodic")
                stats=(profile.cc1 if event.data1==1 else profile.cc11).values if profile else None
                if stats and stats.count:
                    original=int(event.data2 or 0); desired=round(original*(1-strength*.35)+stats.mean*(strength*.35))
                    event.data2=max(0,min(127,desired)); controller_changed+=event.data2!=original
    headroom_report=apply_midi_headroom(result,lambda track,channel,tick:state_for(track,channel,tick)[0],
        mix_profiles,headroom_strength) if mix_headroom and mix_profiles else {"controller_events_changed":0,"controller_events_added":0,"tracks":[]}
    # Solo DNA acts only on lead-like melodic/guitar tracks. It preserves the
    # melody and never invents pitch bend; it shapes phrasing around existing
    # note/controller intent and re-applies the RX articulation guard.
    solo_strength=max(0.,min(1.,float(solo_strength))); solo_channels=set(solo_channels or [])
    solo_candidates=[]; solo_velocity_changed=solo_gate_changed=solo_bend_changed=0
    role_map=lambda track,channel,program: state_for(track,channel,0)[0]
    for feature in extract_features(result,role_map):
        first_tick=min((row["start"] for row in notes if row["track"]==feature.track and row["channel"]==feature.channel),default=0)
        role,rx_name,source_program=state_for(feature.track,feature.channel,first_tick)
        descriptor=solo_descriptor(feature,source_program)
        forced=feature.channel in solo_channels
        if not (forced or descriptor["is_solo_candidate"]) or role not in ("melodic","guitar") or not solo_strength:
            continue
        model=choose_solo_model(solo_models or [],descriptor["family"],tempo_bpm,meter_num,meter_den)
        profile=(model or {}).get("profile",{})
        selected=sorted([row for row in notes if row["track"]==feature.track and row["channel"]==feature.channel],
                        key=lambda row:(row["start"],row["note"]))
        phrases=[]; phrase=[]
        for row in selected:
            if phrase and (row["start"]-(phrase[-1]["start"]+phrase[-1]["duration"]))/midi.division>=.5:
                phrases.append(phrase); phrase=[]
            phrase.append(row)
        if phrase: phrases.append(phrase)
        for phrase in phrases:
            for index,row in enumerate(phrase):
                position=index/max(1,len(phrase)-1)
                arc=2+5*math.sin(math.pi*position)-4*position
                proposed=max(1,min(127,round(row["velocity"]+arc*solo_strength)))
                safe=_protected_velocity(row["velocity"],proposed,rx_name,role,row.get("note"),rx_rules,rx_evidence_audit)
                if safe!=row["velocity"]:
                    row["on_event"].data2=safe; solo_velocity_changed+=1
                if index+1<len(phrase):
                    nxt=phrase[index+1]; target_legato=float(profile.get("legato_ratio",feature.legato_ratio))
                    if target_legato>=.55:
                        desired=min(nxt["start"]+round(.03*midi.division),row["start"]+round(row["duration"]*1.15))
                    else:
                        desired=min(row["off_event"].tick,max(row["start"]+1,nxt["start"]-round(.02*midi.division)))
                    blended=round(row["off_event"].tick*(1-solo_strength)+desired*solo_strength)
                    if blended!=row["off_event"].tick:
                        row["off_event"].tick=max(row["start"]+1,blended); solo_gate_changed+=1
            if phrase:
                last=phrase[-1]; desired=last["start"]+round(last["duration"]*(1+.05*solo_strength))
                if desired!=last["off_event"].tick:
                    last["off_event"].tick=desired; solo_gate_changed+=1
        pitch_events=[event for event in result.tracks[feature.track]
                      if event.kind=="pitch" and int(event.channel or 0)==feature.channel]
        source_range=max((abs(((int(e.data2 or 0)<<7)|int(e.data1 or 0))-8192) for e in pitch_events),default=0)
        target_range=float(profile.get("pitch_bend_range",source_range))
        if source_range and target_range:
            raw_scale=max(.75,min(1.25,target_range/source_range)); scale=1+(raw_scale-1)*solo_strength
            for event in pitch_events:
                value=((int(event.data2 or 0)<<7)|int(event.data1 or 0))-8192
                converted=max(-8192,min(8191,round(value*scale)))+8192
                if converted!=value+8192:
                    event.data1=converted&127; event.data2=(converted>>7)&127; solo_bend_changed+=1
        solo_candidates.append({"track":feature.track,"channel":feature.channel,"role":role,
            "family":descriptor["family"],"score":descriptor["solo_score"],"forced":forced,
            "model":model.get("family") if model else None,"phrases":len(phrases),"notes":len(selected)})
    # Pa800 Guitar Mode uses command notes rather than literal chord pitches.
    # Chord progression velocities (1..24 on C-1..B-1) are semantic data and
    # are never humanized. Strum/string commands retain their command family;
    # deterministic Humanize GTR-like offsets shape position, velocity/length.
    strumming_strength=max(0.,min(1.,float(strumming_strength)))
    strumming_humanize=max(0.,min(1.,float(strumming_humanize))); capo=max(0,min(10,int(capo)))
    strum_model=choose_strumming_model(strumming_models or [],style_section,tempo_bpm,meter_num,meter_den)
    strum_velocity_changed=strum_timing_changed=strum_gate_changed=strum_commands_changed=0
    chord_codes_protected=rx_noise_changed=0
    direction_pairs={24:26,26:24,25:27,27:25,29:31,31:29,32:34,34:32,33:35,35:33}
    for (track,channel),meta in guitar_mode_tracks.items():
        group=sorted(grouped_notes[(track,channel)],key=lambda row:(row["start"],row["note"]))
        previous_direction=None
        for index,row in enumerate(group):
            note=row["note"]
            if 0<=note<=11 and 1<=row["velocity"]<=24:
                chord_codes_protected+=1; continue
            is_command=note in STRUM_COMMANDS or note in STRING_COMMANDS
            is_noise=note>=96
            if not (is_command or is_noise): continue
            strict_gate=bool(rx_rules and rx_rules.get("__report__",{}).get("mode")=="strict")
            if is_noise and strict_gate:
                # Potential RX Noise is recognized for protection only. Until
                # a per-Sound transform claim is admitted, every MIDI field is
                # preserved exactly.
                rx_evidence_audit["noise_events_protected"]+=1
                continue
            position=round((row["start"]/midi.division)*4)%16
            profile=strum_model or {}; velocity_grid=profile.get("velocity_by_16th",{})
            target_velocity=float(velocity_grid.get(str(position),row["velocity"]))
            jitter=((row["start"]*31+note*17+track*7+index*13)%13)-6
            desired=target_velocity+jitter*strumming_humanize
            velocity=max(1,min(127,round(row["velocity"]*(1-strumming_strength)+desired*strumming_strength)))
            if velocity!=row["velocity"]:
                row["on_event"].data2=velocity; strum_velocity_changed+=1
            timing_grid=profile.get("timing_by_16th",{}); learned=float(timing_grid.get(str(position),0))*midi.division
            timing_jitter=jitter*.0025*midi.division*strumming_humanize
            shift=round((learned+timing_jitter)*strumming_strength)
            limit=max(1,round(.025*midi.division)); shift=max(-limit,min(limit,shift)); shift=max(-row["start"],shift)
            if shift:
                row["on_event"].tick+=shift; row["off_event"].tick+=shift; row["start"]+=shift; strum_timing_changed+=1
            gate_scale=1+(jitter/6)*.1*strumming_humanize*strumming_strength
            duration=max(1,round(row["duration"]*gate_scale))
            if duration!=row["duration"]:
                row["off_event"].tick=row["start"]+duration; strum_gate_changed+=1
            if is_noise:
                rx_noise_changed+=velocity!=row["velocity"]; continue
            name=STRUM_COMMANDS.get(note,STRING_COMMANDS.get(note,""))
            direction="down" if "down" in name and "up" not in name else "up" if "up" in name and "down" not in name else None
            alternation=float(profile.get("alternation_ratio",0))
            if (strumming_variation and note in direction_pairs and direction and direction==previous_direction
                    and alternation>=.55 and ((index+row["start"])%100)/100 < strumming_strength):
                new_note=direction_pairs[note]; row["on_event"].data1=new_note; row["off_event"].data1=new_note
                note=new_note; strum_commands_changed+=1
                new_name=STRUM_COMMANDS.get(note,"")
                direction="down" if "down" in new_name and "up" not in new_name else "up"
            if direction: previous_direction=direction
    guitar_repair_report=repair_regular_rhythm_guitars(result,lambda track,channel,tick:state_for(track,channel,tick)[0],
        guitar_repair_strength) if guitar_repair else {"tracks":[],"notes_changed":0,"gate_changed":0,"pitch_notes_changed":0}
    # Solo/Strumming/Guitar Repair run after the main transform. Re-apply only
    # the Factory ceiling (not the mean calibration) so their expressive shape
    # survives but no late stage can make the mix hot again.
    final_headroom_limited=0
    if mix_headroom and mix_profiles:
        for row in note_rows(result):
            role=state_for(row["track"],row["channel"],row["start"])[0]
            safe=soft_limit_velocity(row["velocity"],role,mix_profiles)
            if safe!=row["velocity"]:row["on_event"].data2=safe;final_headroom_limited+=1
    # Prevent a prolonged note from crossing the next onset of the same pitch.
    notes=note_rows(result); groups={}
    for row in notes: groups.setdefault((row["track"],row["channel"],row["note"]),[]).append(row)
    for group in groups.values():
        group.sort(key=lambda row:row["start"])
        for current,nxt in zip(group,group[1:]):
            if current["off_event"].tick>=nxt["start"]:
                current["off_event"].tick=max(current["start"]+1,nxt["start"]-1); overlap_clamps+=1
    return result,{"velocity_notes_changed":cv,"duration_notes_changed":cd,"timing_notes_changed":timing_changed,
        "controller_events_changed":controller_changed,"overlap_clamps":overlap_clamps,"program_changes_mapped":mapped,
        "rx_velocity_notes_protected":protected,"sysex_quarantined":sysex_quarantined,"unmapped_profiles":sorted(unmapped),
        "gold_targets":targets,"gold_model_roles":sorted(gold_model.profiles) if gold_model else [],
        "rx_dna_rules_loaded":sum(len(v) for key,v in (rx_rules or {}).items() if not key.startswith("__")),
        "rx_evidence_gate":{**dict((rx_rules or {}).get("__report__",{})),**dict(rx_evidence_audit)},
        "by_role":role_reports,"strength":strength,
        "solo_strength":solo_strength,"solo_candidates":solo_candidates,"solo_velocity_notes_changed":solo_velocity_changed,
        "solo_gate_notes_changed":solo_gate_changed,"solo_pitch_bend_events_changed":solo_bend_changed,
        "guitar_mode_tracks":[{"track":key[0],"channel":key[1],**value} for key,value in sorted(guitar_mode_tracks.items())],
        "strumming_model":strum_model.get("scope_key") if strum_model else None,"strumming_strength":strumming_strength,
        "strumming_humanize":strumming_humanize,"strumming_capo":capo,
        "strum_velocity_events_changed":strum_velocity_changed,"strum_timing_events_changed":strum_timing_changed,
        "strum_gate_events_changed":strum_gate_changed,"strum_commands_changed":strum_commands_changed,
        "guitar_chord_type_events_protected":chord_codes_protected,"guitar_rx_noise_events_changed":rx_noise_changed,
        "factory_sound_assignments":factory_assigned,"unknown_track_analysis":[value for value in assignments.values() if value.get("unknown_user_sound")],
        "factory_sound_auto_confidence_threshold":auto_sound_threshold,
        "instrument_identity_rejections":identity_rejections,
        "rx_mapping_mode":rx_mapping_mode,"rx_mapping_evidence_rejections":mapping_evidence_rejections,
        "unverified_mappings_applied":unverified_mappings_applied,
        "release_eligible":not unverified_mappings_applied,
        "instrument_identity_gold_corrections":[{"identity":key[0],"role":key[1],**value[1]} for key,value in identity_corrections.items() if value],
        "factory_instrument_structures_used":[{"identity":key[0],"role":key[1],**value[1]} for key,value in factory_structure_choices.items() if value],
        "midi_headroom":headroom_report,"headroom_velocity_notes_limited":headroom_velocity_limited,
        "factory_velocity_notes_calibrated":factory_velocity_calibrated,
        "final_factory_velocity_ceiling_limited":final_headroom_limited,
        "rhythm_guitar_repair":guitar_repair_report}