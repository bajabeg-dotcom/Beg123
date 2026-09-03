"""Deterministic, mutation-free rhythm context for X10 analysis."""

from __future__ import annotations

from bisect import bisect_right
from hashlib import sha256
import json
import math
from math import gcd
from statistics import median

from .midi import MidiFile,note_rows


def _canonical(value)->bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()


def stable_event_id(source_sha256:str,track_index:int,event)->str:
    """Identify an original event without depending on its mutable object id."""
    payload={"source_sha256":source_sha256,"track":int(track_index),"order":float(event.order),
        "kind":event.kind,"channel":event.channel,"tick":int(event.tick),"data1":event.data1,
        "data2":event.data2,"status":event.status,"raw_sha256":sha256(event.raw or b"").hexdigest()}
    return sha256(_canonical(payload)).hexdigest()


def stable_note_id(on_event_id:str,off_event_id:str)->str:
    return sha256(f"{on_event_id}:{off_event_id}".encode()).hexdigest()


def meter_segments(midi:MidiFile)->list[dict]:
    """Build deterministic meter segments; a meter change starts a new bar."""
    changes=[]
    for track,events in enumerate(midi.tracks):
        for event in events:
            if event.kind=="meta" and event.data1==0x58 and len(event.raw)>=2:
                numerator=max(1,int(event.raw[0]));denominator=2**int(event.raw[1])
                changes.append((int(event.tick),track,float(event.order),numerator,denominator))
    changes.sort()
    collapsed=[]
    for tick,track,order,numerator,denominator in changes:
        if collapsed and collapsed[-1][0]==tick:collapsed[-1]=(tick,numerator,denominator)
        else:collapsed.append((tick,numerator,denominator))
    if not collapsed or collapsed[0][0]>0:collapsed.insert(0,(0,4,4))
    elif collapsed[0][0]<0:raise ValueError("Meter event cannot precede tick zero")
    segments=[];bar_base=0
    for index,(tick,numerator,denominator) in enumerate(collapsed):
        if index:
            previous=segments[-1];length=previous["bar_ticks"]
            elapsed=max(0,tick-previous["start_tick"])
            bar_base=previous["bar_base"]+math.ceil(elapsed/length) if elapsed else previous["bar_base"]
        beat_ticks=midi.division*4/denominator;bar_ticks=beat_ticks*numerator
        segments.append({"start_tick":tick,"numerator":numerator,"denominator":denominator,
            "beat_ticks":beat_ticks,"bar_ticks":bar_ticks,"bar_base":bar_base})
    return segments


def position_at_tick(segments:list[dict],tick:int)->dict:
    starts=[segment["start_tick"] for segment in segments]
    segment=segments[max(0,bisect_right(starts,int(tick))-1)]
    relative=max(0,int(tick)-segment["start_tick"]);bar_offset=int(relative//segment["bar_ticks"])
    within_bar=relative-bar_offset*segment["bar_ticks"];beat=int(within_bar//segment["beat_ticks"])
    within_beat=within_bar-beat*segment["beat_ticks"]
    return {"bar":int(segment["bar_base"]+bar_offset),"beat":beat,
        "subbeat_fraction":within_beat/segment["beat_ticks"],"tick_in_bar":int(round(within_bar)),
        "meter_num":segment["numerator"],"meter_den":segment["denominator"],
        "bar_ticks":int(round(segment["bar_ticks"])),"beat_ticks":int(round(segment["beat_ticks"]))}


def extract_rhythm_note_context(midi:MidiFile,source_sha256:str)->list[dict]:
    """Return stable note IDs and multi-scale positions without modifying MIDI."""
    if midi.division<=0:raise ValueError("MIDI division must be positive")
    event_ids={(track,id(event)):stable_event_id(source_sha256,track,event)
        for track,events in enumerate(midi.tracks) for event in events}
    segments=meter_segments(midi);result=[]
    for row in note_rows(midi):
        on_id=event_ids[(row["track"],id(row["on_event"]))];off_id=event_ids[(row["track"],id(row["off_event"]))]
        start=position_at_tick(segments,row["start"]);end=position_at_tick(segments,row["start"]+row["duration"])
        result.append({"note_id":stable_note_id(on_id,off_id),"on_event_id":on_id,"off_event_id":off_id,
            "track":row["track"],"channel":row["channel"],"note":row["note"],"velocity":row["velocity"],
            "start_tick":row["start"],"end_tick":row["start"]+row["duration"],"duration_ticks":row["duration"],
            "duration_quarters":row["duration"]/midi.division,"cross_bar":start["bar"]!=end["bar"],
            **start,"previous_note_id":None,"next_note_id":None})
    groups={}
    for item in result:groups.setdefault((item["track"],item["channel"]),[]).append(item)
    for group in groups.values():
        group.sort(key=lambda item:(item["start_tick"],item["note"],item["note_id"]))
        for index,item in enumerate(group):
            item["previous_note_id"]=group[index-1]["note_id"] if index else None
            item["next_note_id"]=group[index+1]["note_id"] if index+1<len(group) else None
    return sorted(result,key=lambda item:(item["track"],item["start_tick"],item["channel"],item["note"],item["note_id"]))


def bar_pattern_fingerprints(observations:list[dict])->list[dict]:
    """Hash exact within-bar rhythm; no quantization or nearest-grid operation."""
    groups={}
    for item in observations:
        groups.setdefault((item["track"],item["channel"],item["bar"],item["meter_num"],item["meter_den"]),[]).append(item)
    result=[]
    for key,rows in sorted(groups.items()):
        payload=[(row["tick_in_bar"],row["duration_ticks"],row["velocity"],row["note"])
            for row in sorted(rows,key=lambda item:(item["tick_in_bar"],item["note"],item["note_id"]))]
        rhythm_payload=[(row["tick_in_bar"],row["duration_ticks"])
            for row in sorted(rows,key=lambda item:(item["tick_in_bar"],item["note"],item["note_id"]))]
        ordered=sorted(rows,key=lambda item:(item["tick_in_bar"],item["note"],item["note_id"]))
        first_note=ordered[0]["note"] if ordered else 0
        cluster_ticks=sorted({int(row["tick_in_bar"]) for row in ordered})
        cluster_index={tick:index for index,tick in enumerate(cluster_ticks)}
        cluster_sizes=[sum(int(row["tick_in_bar"])==tick for row in ordered) for tick in cluster_ticks]
        onset_intervals=[]
        for first,second in zip(cluster_ticks,cluster_ticks[1:]):
            interval=max(0,second-first);divisor=gcd(max(1,interval),max(1,int(ordered[0]["bar_ticks"])))
            onset_intervals.append((interval//divisor,int(ordered[0]["bar_ticks"])//divisor))
        voice_payload=[]
        for index,row in enumerate(ordered):
            divisor=gcd(max(1,int(row["duration_ticks"])),max(1,int(row["bar_ticks"])))
            voice_payload.append((cluster_index[int(row["tick_in_bar"])],row["note"]-first_note,
                int(row["duration_ticks"])//divisor,int(row["bar_ticks"])//divisor))
        topology_payload={"cluster_sizes":cluster_sizes,"onset_intervals":onset_intervals,"voices":voice_payload}
        velocities=[row["velocity"] for row in ordered]
        velocity_center=median(velocities) if velocities else 0
        accent_payload=[-1 if value<velocity_center else 1 if value>velocity_center else 0 for value in velocities]
        result.append({"track":key[0],"channel":key[1],"bar":key[2],"meter_num":key[3],"meter_den":key[4],
            "event_count":len(rows),"onset_cluster_count":len(cluster_ticks),"pattern_sha256":sha256(_canonical(payload)).hexdigest(),
            "rhythm_pattern_sha256":sha256(_canonical(rhythm_payload)).hexdigest(),
            "topology_sha256":sha256(_canonical(topology_payload)).hexdigest(),
            "accent_sha256":sha256(_canonical(accent_payload)).hexdigest(),
            "exact_payload":payload,"rhythm_payload":rhythm_payload,"topology_payload":topology_payload})
    return result


def phrase_candidates(observations:list[dict])->list[dict]:
    """Segment conservative phrase candidates; every boundary stays heuristic."""
    groups={}
    for item in observations:groups.setdefault((item["track"],item["channel"]),[]).append(item)
    output=[]
    for (track,channel),rows in sorted(groups.items()):
        rows.sort(key=lambda item:(item["start_tick"],item["note"],item["note_id"]));phrases=[];current=[]
        for row in rows:
            if current:
                previous=current[-1];gap=row["start_tick"]-previous["end_tick"]
                empty_bar_gap=row["bar"]-previous["bar"]>=2
                beat_gap=gap>=max(1,row["beat_ticks"])
                if empty_bar_gap or beat_gap:
                    phrases.append((current,"EMPTY_BAR" if empty_bar_gap else "REST_AT_LEAST_ONE_BEAT"));current=[]
            current.append(row)
        if current:phrases.append((current,"END_OF_TRACK_CHANNEL"))
        for index,(phrase,end_reason) in enumerate(phrases):
            note_ids=[row["note_id"] for row in phrase]
            output.append({"phrase_id":sha256(_canonical(note_ids)).hexdigest(),"track":track,"channel":channel,
                "phrase_index":index,"start_tick":phrase[0]["start_tick"],"end_tick":max(row["end_tick"] for row in phrase),
                "start_bar":phrase[0]["bar"],"end_bar":max(row["bar"] for row in phrase),"note_count":len(phrase),
                "cross_bar":any(row["cross_bar"] for row in phrase) or phrase[0]["bar"]!=phrase[-1]["bar"],
                "boundary_status":"HEURISTIC_CANDIDATE","end_reason":end_reason,"note_ids":note_ids})
    return output


def multi_bar_candidates(observations:list[dict],window_sizes:tuple[int,...]=(2,4))->list[dict]:
    """Find repeated exact rhythm sequences across consecutive bars."""
    bars=bar_pattern_fingerprints(observations);groups={}
    for bar in bars:groups.setdefault((bar["track"],bar["channel"]),[]).append(bar)
    instances=[]
    for (track,channel),rows in sorted(groups.items()):
        rows.sort(key=lambda item:item["bar"])
        for size in sorted(set(int(value) for value in window_sizes if int(value)>1)):
            for index in range(len(rows)-size+1):
                selected=rows[index:index+size]
                if any(second["bar"]!=first["bar"]+1 for first,second in zip(selected,selected[1:])):continue
                sequence=[row["rhythm_pattern_sha256"] for row in selected]
                instances.append({"track":track,"channel":channel,"window_bars":size,"start_bar":selected[0]["bar"],
                    "end_bar":selected[-1]["bar"],"sequence_sha256":sha256(_canonical(sequence)).hexdigest(),
                    "bar_pattern_ids":sequence})
    counts={}
    for item in instances:counts[(item["track"],item["channel"],item["window_bars"],item["sequence_sha256"])]=counts.get(
        (item["track"],item["channel"],item["window_bars"],item["sequence_sha256"]),0)+1
    for item in instances:item["occurrence_count"]=counts[(item["track"],item["channel"],item["window_bars"],item["sequence_sha256"])]
    return instances