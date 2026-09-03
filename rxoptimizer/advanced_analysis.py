"""Deep, read-only MIDI diagnostics for proposed advanced DNA modules."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Iterable

from .features import extract_features, infer_role
from .midi import MidiFile, note_rows, parse_midi, validate_midi


def _texts(events, meta_type: int) -> list[str]:
    return [event.raw.decode("latin1", "replace").strip(" \x00") for event in events
            if event.kind == "meta" and event.data1 == meta_type and event.raw]


def _tempo_meter(midi: MidiFile) -> tuple[float | None, tuple[int, int]]:
    tempo=None; meter=(4,4)
    for events in midi.tracks:
        for event in events:
            if event.kind=="meta" and event.data1==0x51 and len(event.raw)==3 and tempo is None:
                micros=int.from_bytes(event.raw,"big"); tempo=60_000_000/micros if micros else None
            elif event.kind=="meta" and event.data1==0x58 and len(event.raw)>=2:
                meter=(int(event.raw[0]),2**int(event.raw[1]))
    return tempo,meter


def _program_state(events) -> dict[int, tuple[int,int,int]]:
    banks={channel:[0,0] for channel in range(16)}; result={}
    for event in sorted(events,key=lambda e:(e.tick,e.order)):
        channel=int(event.channel or 0)
        if event.kind=="control" and event.data1 in (0,32):
            banks[channel][0 if event.data1==0 else 1]=int(event.data2 or 0)
        elif event.kind=="program":
            result[channel]=(*banks[channel],int(event.data1 or 0))
    return result


def _ornaments(rows: list[dict], division: int) -> dict:
    rows=sorted(rows,key=lambda row:(row["start"],row["note"])); quarter=division
    grace=sum(row["duration"]<=.125*quarter for row in rows)
    trills=[]; tremolos=[]; neighbor_figures=[]
    consumed_trill=set(); consumed_tremolo=set()
    for start in range(len(rows)-3):
        first,second=rows[start],rows[start+1]
        if first["duration"]>.35*quarter or second["duration"]>.35*quarter: continue
        if second["start"]-first["start"]>.3*quarter: continue
        if 1<=abs(second["note"]-first["note"])<=3:
            cursor=start+2
            while cursor<len(rows) and rows[cursor]["duration"]<=.35*quarter and rows[cursor]["start"]-rows[cursor-1]["start"]<=.3*quarter and rows[cursor]["note"]==rows[start+(cursor-start)%2]["note"]:
                cursor+=1
            if cursor-start>=4 and not any(index in consumed_trill for index in range(start,cursor)):
                trills.append({"start":first["start"],"notes":cursor-start,
                    "pitches":sorted({row["note"] for row in rows[start:cursor]})})
                consumed_trill.update(range(start,cursor))
        cursor=start+1
        while cursor<len(rows) and rows[cursor]["note"]==first["note"] and rows[cursor]["duration"]<=.35*quarter and rows[cursor]["start"]-rows[cursor-1]["start"]<=.3*quarter:
            cursor+=1
        if cursor-start>=4 and not any(index in consumed_tremolo for index in range(start,cursor)):
            tremolos.append({"start":first["start"],"notes":cursor-start,"pitch":first["note"]})
            consumed_tremolo.update(range(start,cursor))
    for start in range(len(rows)-2):
        fragment=[row["note"] for row in rows[start:start+3]]
        span=rows[start+2]["start"]-rows[start]["start"]
        if span<=.75*quarter and fragment[0]==fragment[2] and 1<=abs(fragment[1]-fragment[0])<=3:
            neighbor_figures.append({"start":rows[start]["start"],"pattern":fragment})
    for start in range(len(rows)-3):
        fragment=[row["note"] for row in rows[start:start+4]]
        span=rows[start+3]["start"]-rows[start]["start"]
        if span<=.75*quarter and fragment[0]==fragment[3] and max(fragment)-min(fragment)<=4:
            neighbor_figures.append({"start":rows[start]["start"],"pattern":fragment})
    return {"grace_notes":grace,"trill_sequences":trills,"trill_count":len(trills),
            "tremolo_sequences":tremolos,"tremolo_count":len(tremolos),
            "neighbor_ornaments":neighbor_figures[:100],"neighbor_ornament_count":len(neighbor_figures)}


def _power_chords(rows: list[dict], division: int) -> dict:
    starts=defaultdict(list)
    for row in rows: starts[row["start"]].append(row["note"])
    dyads=[]
    for tick,pitches in starts.items():
        unique=sorted(set(pitches))
        pcs={pitch%12 for pitch in unique}
        for root in unique:
            if (root+7)%12 in pcs and (root+3)%12 not in pcs and (root+4)%12 not in pcs:
                dyads.append({"tick":tick,"root":root%12,"notes":unique}); break
    return {"power_chord_events":len(dyads),"examples":dyads[:30]}


def _echo_offsets(rows: list[dict], division: int) -> list[dict]:
    by_pitch=defaultdict(dict)
    for row in rows: by_pitch[row["note"]][row["start"]]=row["velocity"]
    offsets=sorted(set([round(division*x) for x in (.125,.25,1/3,.5,.75,1,1.5,2)]))
    result=[]
    for offset in offsets:
        matches=lower=total=0
        for pitch,ticks in by_pitch.items():
            for tick,velocity in ticks.items():
                total+=1
                if tick+offset in ticks:
                    matches+=1; lower+=ticks[tick+offset]<velocity
        score=matches/max(1,total)
        if matches>=4 and score>=.03:
            result.append({"offset_ticks":offset,"offset_quarters":round(offset/division,4),
                "matches":matches,"lower_velocity_matches":lower,"score":round(score,4)})
    return sorted(result,key=lambda item:(-item["score"],item["offset_ticks"]))


def _bar_features(midi: MidiFile, rows: list[dict], meter: tuple[int,int]) -> list[dict]:
    bar_quarters=meter[0]*4/meter[1]; bar_ticks=max(1,round(bar_quarters*midi.division))
    maximum=max((row["start"]+row["duration"] for row in rows),default=0); bars=[]
    for start in range(0,maximum+1,bar_ticks):
        selected=[row for row in rows if start<=row["start"]<start+bar_ticks]
        drum=[row for row in selected if row["channel"]==9]
        melodic=[row for row in selected if row["channel"]!=9]
        crash=sum(row["note"] in (49,52,55,57) for row in drum)
        toms=sum(41<=row["note"]<=50 for row in drum)
        bars.append({"bar":len(bars)+1,"start_tick":start,"notes":len(selected),"drum_notes":len(drum),
            "melodic_notes":len(melodic),"crash":crash,"toms":toms,
            "velocity_mean":round(mean([row["velocity"] for row in selected]),2) if selected else 0})
    drum_values=[bar["drum_notes"] for bar in bars]
    baseline=median(drum_values) if drum_values else 0
    spread=pstdev(drum_values) if len(drum_values)>1 else 0
    for bar in bars:
        bar["fill_score"]=round((bar["drum_notes"]-baseline)/max(1,spread)+bar["toms"]*.15+bar["crash"]*.25,3)
        bar["break_candidate"]=bar["notes"]<=max(2,median([x["notes"] for x in bars])*.25) if bars else False
    return bars


def _cross_track_delays(groups: dict[tuple[int,int],list[dict]], division: int) -> list[dict]:
    keys=list(groups); offsets=sorted(set(round(division*x) for x in (.125,.25,1/3,.5,.75,1,1.5,2)))
    signatures={key:{(row["start"],row["note"]):row["velocity"] for row in value} for key,value in groups.items()}
    found=[]
    for i,left in enumerate(keys):
        if len(signatures[left])<8: continue
        for right in keys[i+1:]:
            if len(signatures[right])<8: continue
            for offset in offsets:
                matches=lower=0
                for (tick,note),velocity in signatures[left].items():
                    target=signatures[right].get((tick+offset,note))
                    if target is not None: matches+=1; lower+=target<velocity
                score=matches/max(1,min(len(signatures[left]),len(signatures[right])))
                if matches>=8 and score>=.25:
                    found.append({"source":{"track":left[0],"channel":left[1]},"echo":{"track":right[0],"channel":right[1]},
                        "offset_quarters":round(offset/division,4),"matches":matches,"score":round(score,4),
                        "lower_velocity_ratio":round(lower/max(1,matches),4)})
    return sorted(found,key=lambda item:-item["score"])


def analyze_midi(path: Path) -> dict:
    midi=parse_midi(path.read_bytes()); validation=validate_midi(midi); tempo,meter=_tempo_meter(midi)
    all_rows=note_rows(midi); groups=defaultdict(list)
    for row in all_rows: groups[(row["track"],row["channel"])].append(row)
    feature_index={(feature.track,feature.channel):feature for feature in extract_features(midi)}
    tracks=[]
    for track_index,events in enumerate(midi.tracks):
        programs=_program_state(events); names=_texts(events,3); instruments=_texts(events,1)
        controllers=Counter(int(event.data1) for event in events if event.kind=="control" and event.data1 is not None)
        event_counts=Counter(event.kind for event in events)
        channels=sorted({int(event.channel or 0) for event in events if event.channel is not None})
        if not channels and events:
            tracks.append({"track":track_index,"track_names":names,"instrument_texts":instruments,
                "event_counts":dict(event_counts),"channels":[]}); continue
        for channel in channels:
            selected=groups.get((track_index,channel),[]); feature=feature_index.get((track_index,channel))
            bank_program=programs.get(channel,(0,0,0)); role=infer_role(channel,bank_program[2])
            pitch_events=[event for event in events if event.kind=="pitch" and int(event.channel or 0)==channel]
            pressure_events=[event for event in events if event.kind in ("pressure","poly_pressure") and int(event.channel or 0)==channel]
            bend_values=[((int(event.data2 or 0)<<7)|int(event.data1 or 0))-8192 for event in pitch_events]
            ornaments=_ornaments(selected,midi.division) if selected and role not in ("drums","percussion") else {
                "grace_notes":0,"trill_sequences":[],"trill_count":0,"tremolo_sequences":[],
                "tremolo_count":0,"neighbor_ornaments":[],"neighbor_ornament_count":0}
            power=_power_chords(selected,midi.division) if selected else {}
            tracks.append({"track":track_index,"channel":channel,"track_names":names,"instrument_texts":instruments,
                "role":role,"bank_msb":bank_program[0],"bank_lsb":bank_program[1],"program":bank_program[2],
                "note_count":len(selected),"pitch_min":min((row["note"] for row in selected),default=None),
                "pitch_max":max((row["note"] for row in selected),default=None),
                "velocity_mean":round(mean([row["velocity"] for row in selected]),3) if selected else None,
                "duration_quarters":round(mean([row["duration"]/midi.division for row in selected]),4) if selected else None,
                "density_per_quarter":round(feature.density_per_quarter,4) if feature else 0,
                "monophony_ratio":round(feature.monophony_ratio,4) if feature else 0,
                "legato_ratio":round(feature.legato_ratio,4) if feature else 0,
                "pitch_bend_events":len(pitch_events),"pitch_bend_range":max((abs(value) for value in bend_values),default=0),
                "pressure_events":len(pressure_events),"controllers":dict(controllers),
                "noise_note_count":sum(row["note"]>=96 for row in selected) if role in ("melodic","guitar") else 0,
                "ornaments":ornaments,"power_chords":power,"echo_offsets":_echo_offsets(selected,midi.division) if selected else []})
    bars=_bar_features(midi,all_rows,meter)
    fill_candidates=sorted([bar for bar in bars if bar["fill_score"]>=2],key=lambda bar:-bar["fill_score"])
    return {"filename":path.name,"bytes":path.stat().st_size,"format":midi.format,"division":midi.division,
        "track_chunks":len(midi.tracks),"tempo_bpm":round(tempo,3) if tempo else None,"meter":f"{meter[0]}/{meter[1]}",
        "validation":validation,"total_notes":len(all_rows),"tracks":tracks,"bar_count":len(bars),
        "fill_candidates":fill_candidates[:30],"break_candidates":[bar for bar in bars if bar["break_candidate"]][:30],
        "cross_track_delay_candidates":_cross_track_delays(groups,midi.division),
        "markers":[text for events in midi.tracks for kind in (6,7) for text in _texts(events,kind)]}


def analyze_paths(paths: Iterable[Path]) -> list[dict]:
    return [analyze_midi(path) for path in paths]