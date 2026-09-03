"""Dependency-free Standard MIDI File reader/writer."""

from __future__ import annotations
from dataclasses import dataclass, field
import struct


class MidiError(ValueError):
    pass


def read_vlq(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        if pos >= len(data):
            raise MidiError("Neočekivan kraj VLQ vrijednosti")
        byte = data[pos]; pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, pos
    raise MidiError("Nevažeća VLQ vrijednost")


def write_vlq(value: int) -> bytes:
    value = max(0, int(value)); result = [value & 0x7F]; value >>= 7
    while value:
        result.append(0x80 | (value & 0x7F)); value >>= 7
    return bytes(reversed(result))


@dataclass
class Event:
    tick: int
    order: float
    kind: str
    channel: int | None = None
    data1: int | None = None
    data2: int | None = None
    status: int | None = None
    raw: bytes = b""


@dataclass
class MidiFile:
    format: int
    division: int
    tracks: list[list[Event]] = field(default_factory=list)


def parse_midi(data: bytes) -> MidiFile:
    if len(data) < 14 or data[:4] != b"MThd":
        raise MidiError("Fajl nije Standard MIDI File")
    header_len = struct.unpack(">I", data[4:8])[0]
    if header_len < 6 or 8 + header_len > len(data):
        raise MidiError("Nevažeća dužina MIDI zaglavlja")
    fmt, track_count, division = struct.unpack(">HHH", data[8:14])
    if division & 0x8000:
        raise MidiError("SMPTE time division nije podržan")
    pos = 8 + header_len; tracks = []
    for _ in range(track_count):
        if pos + 8 > len(data):
            raise MidiError("Prekinut MTrk header")
        if data[pos:pos + 4] != b"MTrk":
            raise MidiError("Nedostaje MTrk blok")
        length = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        if pos + 8 + length > len(data):
            raise MidiError("Deklarisana MTrk dužina prelazi fajl")
        tracks.append(_parse_track(data[pos + 8:pos + 8 + length]))
        pos += 8 + length
    return MidiFile(fmt, division, tracks)


def _parse_track(chunk: bytes) -> list[Event]:
    events = []; pos = tick = order = 0; running = None
    while pos < len(chunk):
        delta, pos = read_vlq(chunk, pos); tick += delta
        if pos >= len(chunk): raise MidiError("Prekinut MIDI događaj")
        if chunk[pos] & 0x80:
            status = chunk[pos]; pos += 1
        elif running is not None:
            status = running
        else:
            raise MidiError("Running status bez prethodnog statusa")
        if status == 0xFF:
            running = None
            if pos >= len(chunk): raise MidiError("Prekinut meta tip")
            meta_type = chunk[pos]; pos += 1
            size, pos = read_vlq(chunk, pos)
            if pos + size > len(chunk): raise MidiError("Prekinut meta payload")
            payload = chunk[pos:pos + size]; pos += size
            events.append(Event(tick, order, "meta", data1=meta_type, raw=payload))
        elif status in (0xF0, 0xF7):
            running = None; size, pos = read_vlq(chunk, pos)
            if pos + size > len(chunk): raise MidiError("Prekinut SysEx payload")
            payload = chunk[pos:pos + size]; pos += size
            events.append(Event(tick, order, "sysex", status=status, raw=payload))
        else:
            running = status; family = status & 0xF0; channel = status & 0x0F
            size = 1 if family in (0xC0, 0xD0) else 2
            if pos + size > len(chunk): raise MidiError("Prekinuta channel poruka")
            d1 = chunk[pos]; d2 = chunk[pos + 1] if size == 2 else None; pos += size
            kind = {0x80:"note_off",0x90:"note_on",0xA0:"poly_pressure",0xB0:"control",0xC0:"program",0xD0:"pressure",0xE0:"pitch"}.get(family,"channel")
            if kind == "note_on" and d2 == 0: kind = "note_off"
            events.append(Event(tick, order, kind, channel, d1, d2, status))
        order += 1
    return events


def encode_midi(midi: MidiFile) -> bytes:
    header = b"MThd" + struct.pack(">IHHH", 6, midi.format, len(midi.tracks), midi.division)
    chunks = []
    for events in midi.tracks:
        body = bytearray(); previous = 0
        # End-of-Track must be the final event, including after optimized
        # note-offs that may have moved beyond the original EOT tick.
        ordered = sorted((e for e in events if not (e.kind=="meta" and e.data1==0x2F)), key=lambda e:(e.tick,e.order))
        ordered.append(Event(max((e.tick for e in ordered),default=0),10**9,"meta",data1=0x2F))
        for event in ordered:
            body.extend(write_vlq(event.tick - previous)); previous = event.tick
            if event.kind == "meta":
                body.extend((0xFF,int(event.data1 or 0))); body.extend(write_vlq(len(event.raw))); body.extend(event.raw)
            elif event.kind == "sysex":
                body.append(int(event.status or 0xF0)); body.extend(write_vlq(len(event.raw))); body.extend(event.raw)
            else:
                status = int(event.status or _status_for(event)); body.extend((status,int(event.data1 or 0)))
                if (status & 0xF0) not in (0xC0,0xD0): body.append(int(event.data2 or 0))
        chunks.append(b"MTrk" + struct.pack(">I",len(body)) + bytes(body))
    return header + b"".join(chunks)


def _status_for(event: Event) -> int:
    family = {"note_off":0x80,"note_on":0x90,"poly_pressure":0xA0,"control":0xB0,"program":0xC0,"pressure":0xD0,"pitch":0xE0}[event.kind]
    return family | int(event.channel or 0)


def note_rows(midi: MidiFile) -> list[dict]:
    rows = []
    for track_index, events in enumerate(midi.tracks):
        active = {}
        for event in sorted(events,key=lambda e:(e.tick,e.order)):
            key = (int(event.channel or 0),int(event.data1 or 0))
            if event.kind == "note_on" and event.data2:
                active.setdefault(key,[]).append(event)
            elif event.kind == "note_off" and active.get(key):
                start = active[key].pop(0)
                rows.append({"track":track_index,"channel":key[0],"note":key[1],"start":start.tick,
                    "duration":max(1,event.tick-start.tick),"velocity":int(start.data2 or 1),"on_event":start,"off_event":event})
    return rows


def validate_midi(midi: MidiFile) -> dict:
    """Return semantic invariants used before accepting an optimizer export."""
    unmatched_off=invalid_values=0; active={}; note_on=note_off=0
    for track_index,events in enumerate(midi.tracks):
        for event in sorted(events,key=lambda e:(e.tick,e.order)):
            for value in (event.data1,event.data2):
                if value is not None and not 0 <= int(value) <= 127: invalid_values+=1
            if event.channel is not None and not 0 <= int(event.channel) <= 15: invalid_values+=1
            if event.kind=="note_on" and int(event.data2 or 0)>0:
                key=(track_index,int(event.channel or 0),int(event.data1 or 0)); active[key]=active.get(key,0)+1; note_on+=1
            elif event.kind=="note_off":
                key=(track_index,int(event.channel or 0),int(event.data1 or 0)); note_off+=1
                if active.get(key,0): active[key]-=1
                else: unmatched_off+=1
    unmatched_on=sum(active.values())
    return {"note_on":note_on,"note_off":note_off,"unmatched_note_on":unmatched_on,
            "unmatched_note_off":unmatched_off,"invalid_values":invalid_values,
            "valid":invalid_values==0 and unmatched_on==0 and unmatched_off==0}