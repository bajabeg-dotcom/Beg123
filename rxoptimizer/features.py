"""Musical feature extraction and deterministic Gold DNA profiles.

The module deliberately does not mutate :class:`~rxoptimizer.midi.MidiFile`.
It turns MIDI events (and, optionally, database ``track_stats`` rows) into
small, JSON-friendly role profiles that an optimizer can consume later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Callable, Iterable, Mapping, Sequence

import numpy as np

from .midi import MidiFile, note_rows


RoleMap = Mapping[tuple[int, int], str] | Callable[[int, int, int | None], str]


@dataclass(frozen=True)
class ScalarStats:
    """A mergeable population summary."""

    count: int = 0
    mean: float = 0.0
    std: float = 0.0
    minimum: float = 0.0
    maximum: float = 0.0

    @classmethod
    def from_values(cls, values: Iterable[float]) -> "ScalarStats":
        data = np.asarray(list(values), dtype=float)
        if not data.size:
            return cls()
        return cls(
            int(data.size), float(data.mean()), float(data.std()),
            float(data.min()), float(data.max()),
        )

    @classmethod
    def merge(cls, values: Iterable["ScalarStats"]) -> "ScalarStats":
        summaries = [value for value in values if value.count]
        if not summaries:
            return cls()
        count = sum(value.count for value in summaries)
        mean = sum(value.mean * value.count for value in summaries) / count
        variance = sum(
            value.count * (value.std ** 2 + (value.mean - mean) ** 2)
            for value in summaries
        ) / count
        return cls(
            count, mean, math.sqrt(max(0.0, variance)),
            min(value.minimum for value in summaries),
            max(value.maximum for value in summaries),
        )


@dataclass(frozen=True)
class CCStats:
    values: ScalarStats = field(default_factory=ScalarStats)
    changes_per_quarter: float = 0.0


@dataclass(frozen=True)
class TrackFeatures:
    track: int
    channel: int
    role: str
    note_count: int
    length_quarters: float
    density_per_quarter: float
    velocity: ScalarStats
    duration_quarters: ScalarStats
    timing_offset_quarters: ScalarStats
    swing_ratio: ScalarStats
    velocity_by_16th: tuple[ScalarStats, ...]
    timing_by_16th: tuple[ScalarStats, ...]
    cc1: CCStats
    cc11: CCStats
    pitch: ScalarStats = field(default_factory=ScalarStats)
    interval_abs: ScalarStats = field(default_factory=ScalarStats)
    rest_quarters: ScalarStats = field(default_factory=ScalarStats)
    monophony_ratio: float = 0.0
    overlap_ratio: float = 0.0
    legato_ratio: float = 0.0
    step_ratio: float = 0.0
    leap_ratio: float = 0.0
    repeated_note_ratio: float = 0.0
    phrase_count: int = 0
    phrase_length_notes: ScalarStats = field(default_factory=ScalarStats)
    pitch_bend: CCStats = field(default_factory=CCStats)
    pressure: CCStats = field(default_factory=CCStats)


@dataclass(frozen=True)
class RoleProfile:
    role: str
    track_count: int
    note_count: int
    velocity: ScalarStats
    duration_quarters: ScalarStats
    timing_offset_quarters: ScalarStats
    swing_ratio: ScalarStats
    density_per_quarter: float
    velocity_by_16th: tuple[ScalarStats, ...]
    timing_by_16th: tuple[ScalarStats, ...]
    cc1: CCStats
    cc11: CCStats


def _programs(midi: MidiFile) -> dict[tuple[int, int], int]:
    programs: dict[tuple[int, int], int] = {}
    for track_index, events in enumerate(midi.tracks):
        for event in sorted(events, key=lambda item: (item.tick, item.order)):
            if event.kind == "program":
                programs[(track_index, int(event.channel or 0))] = int(event.data1 or 0)
    return programs


def infer_role(channel: int, program: int | None = None) -> str:
    """Infer the same broad arranger role without depending on optimizer.py."""

    if channel == 9:
        return "drums"
    if channel == 8 or (program is not None and 32 <= program <= 39):
        return "bass"
    if program is not None and 24 <= program <= 31:
        return "guitar"
    if channel == 10:
        return "percussion"
    if 11 <= channel <= 15:
        return "accompaniment"
    return "melodic"


def _resolve_role(
    role_map: RoleMap | None, track: int, channel: int, program: int | None
) -> str:
    if callable(role_map):
        return str(role_map(track, channel, program))
    if role_map and (track, channel) in role_map:
        return str(role_map[(track, channel)])
    return infer_role(channel, program)


def _swing_ratios(onsets: np.ndarray, length_quarters: float) -> list[float]:
    """Return local first/second eighth-note ratios (1=straight, 2=triplet)."""

    if onsets.size < 3:
        return []
    ratios: list[float] = []
    tolerance = 0.24
    for beat in range(max(0, int(math.floor(length_quarters)))):
        anchors = []
        for target in (float(beat), beat + 0.5, beat + 1.0):
            index = int(np.argmin(np.abs(onsets - target)))
            value = float(onsets[index])
            if abs(value - target) > tolerance:
                anchors = []
                break
            anchors.append(value)
        if len(anchors) == 3:
            first, second = anchors[1] - anchors[0], anchors[2] - anchors[1]
            if first > 0 and second > 0:
                ratios.append(first / second)
    return ratios


def _cc_stats(events, channel: int, controller: int, length: float) -> CCStats:
    values = [
        int(event.data2 or 0) for event in events
        if event.kind == "control" and int(event.channel or 0) == channel
        and event.data1 == controller
    ]
    return CCStats(ScalarStats.from_values(values), len(values) / max(length, 1e-9))


def _event_stats(events, channel: int, kinds: tuple[str, ...], length: float) -> CCStats:
    values = []
    for event in events:
        if event.kind not in kinds or int(event.channel or 0) != channel:
            continue
        if event.kind == "pitch":
            values.append(((int(event.data2 or 0) << 7) | int(event.data1 or 0)) - 8192)
        else:
            values.append(int(event.data1 or 0))
    return CCStats(ScalarStats.from_values(values), len(values) / max(length, 1e-9))


def extract_features(midi: MidiFile, role_map: RoleMap | None = None) -> list[TrackFeatures]:
    """Extract role-aware features for every track/channel containing notes.

    Timing is represented as distance from the nearest 16th-note grid point,
    measured in quarter notes. ``velocity_by_16th`` and ``timing_by_16th`` are
    fixed 16-element tuples (one 4/4 bar), so profiles remain easy to persist.
    """

    if midi.division <= 0:
        raise ValueError("MIDI division must be positive")
    programs = _programs(midi)
    rows = note_rows(midi)
    groups: dict[tuple[int, int], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["track"], row["channel"]), []).append(row)

    result: list[TrackFeatures] = []
    for (track, channel), selected in sorted(groups.items()):
        events = midi.tracks[track]
        length_ticks = max(
            [int(event.tick) for event in events]
            + [int(row["start"] + row["duration"]) for row in selected]
        )
        length = max(length_ticks / midi.division, 1 / midi.division)
        starts = np.asarray([row["start"] / midi.division for row in selected], dtype=float)
        durations = np.asarray([row["duration"] / midi.division for row in selected], dtype=float)
        velocities = np.asarray([row["velocity"] for row in selected], dtype=float)
        pitches = np.asarray([row["note"] for row in selected], dtype=float)
        chronological = sorted(selected, key=lambda row: (row["start"], row["note"]))
        pairs = list(zip(chronological, chronological[1:]))
        intervals = [abs(second["note"] - first["note"]) for first, second in pairs]
        rests = [max(0.0, (second["start"] - first["start"] - first["duration"]) / midi.division)
                 for first, second in pairs]
        overlaps = sum(second["start"] < first["start"] + first["duration"] for first, second in pairs)
        legato = sum((second["start"] - first["start"] - first["duration"]) / midi.division <= .05
                     for first, second in pairs)
        phrase_lengths = []
        current_phrase = 1 if chronological else 0
        for rest in rests:
            if rest >= .5:
                phrase_lengths.append(current_phrase); current_phrase = 1
            else:
                current_phrase += 1
        if current_phrase:
            phrase_lengths.append(current_phrase)
        transition_count = max(1, len(pairs))
        # MIDI ticks are non-negative. Half-up avoids NumPy's banker's rounding
        # choosing different grid sides for exact eighth-of-a-quarter ties.
        grid = np.floor(starts * 4 + 0.5).astype(int)
        positions = np.mod(grid, 16)
        offsets = starts - grid / 4.0
        velocity_bins = tuple(
            ScalarStats.from_values(velocities[positions == position])
            for position in range(16)
        )
        timing_bins = tuple(
            ScalarStats.from_values(offsets[positions == position])
            for position in range(16)
        )
        role = _resolve_role(role_map, track, channel, programs.get((track, channel)))
        result.append(TrackFeatures(
            track=track,
            channel=channel,
            role=role,
            note_count=len(selected),
            length_quarters=length,
            density_per_quarter=len(selected) / length,
            velocity=ScalarStats.from_values(velocities),
            duration_quarters=ScalarStats.from_values(durations),
            timing_offset_quarters=ScalarStats.from_values(offsets),
            swing_ratio=ScalarStats.from_values(_swing_ratios(np.unique(starts), length)),
            velocity_by_16th=velocity_bins,
            timing_by_16th=timing_bins,
            cc1=_cc_stats(events, channel, 1, length),
            cc11=_cc_stats(events, channel, 11, length),
            pitch=ScalarStats.from_values(pitches),
            interval_abs=ScalarStats.from_values(intervals),
            rest_quarters=ScalarStats.from_values(rests),
            monophony_ratio=1.0 - overlaps / transition_count,
            overlap_ratio=overlaps / transition_count,
            legato_ratio=legato / transition_count,
            step_ratio=sum(0 < value <= 2 for value in intervals) / transition_count,
            leap_ratio=sum(value >= 5 for value in intervals) / transition_count,
            repeated_note_ratio=sum(value == 0 for value in intervals) / transition_count,
            phrase_count=len(phrase_lengths),
            phrase_length_notes=ScalarStats.from_values(phrase_lengths),
            pitch_bend=_event_stats(events, channel, ("pitch",), length),
            pressure=_event_stats(events, channel, ("pressure", "poly_pressure"), length),
        ))
    return result


def _row_value(row, key: str, default=None):
    if isinstance(row, Mapping):
        return row.get(key, default)
    try:
        return row[key]
    except (IndexError, KeyError, TypeError):
        return getattr(row, key, default)


def _summary_from_track_rows(
    rows, key: str, fallback_key: str | None = None, std_key: str | None = None
) -> ScalarStats:
    summaries = []
    for row in rows:
        count = int(_row_value(row, "note_count", 0) or 0)
        value = _row_value(row, key)
        if value is None and fallback_key:
            value = _row_value(row, fallback_key)
        if count and value is not None:
            standard_deviation = float(_row_value(row, std_key, 0) or 0) if std_key else 0.0
            summaries.append(ScalarStats(
                count, float(value), standard_deviation, float(value), float(value)
            ))
    return ScalarStats.merge(summaries)


def aggregate_profiles(
    features: Iterable[TrackFeatures], track_stats: Iterable[Mapping] = ()
) -> dict[str, RoleProfile]:
    """Aggregate event features plus optional SQLite ``track_stats`` rows.

    Database rows enrich overall velocity/duration/density. Event-derived
    beat-position, swing and controller data stay exact and are not invented
    for legacy rows that do not contain those columns.
    """

    feature_list = list(features)
    stat_list = list(track_stats)
    roles = sorted(
        {item.role for item in feature_list}
        | {str(_row_value(row, "role", "melodic")) for row in stat_list}
    )
    profiles: dict[str, RoleProfile] = {}
    for role in roles:
        selected = [item for item in feature_list if item.role == role]
        rows = [row for row in stat_list if str(_row_value(row, "role", "melodic")) == role]
        event_velocity = ScalarStats.merge(item.velocity for item in selected)
        db_velocity = _summary_from_track_rows(rows, "velocity_mean", std_key="velocity_std")
        event_duration = ScalarStats.merge(item.duration_quarters for item in selected)
        db_duration = _summary_from_track_rows(rows, "duration_quarters")
        velocity = ScalarStats.merge((event_velocity, db_velocity))
        duration = ScalarStats.merge((event_duration, db_duration))
        note_count = sum(item.note_count for item in selected) + sum(
            int(_row_value(row, "note_count", 0) or 0) for row in rows
        )
        density_weighted = [
            (item.density_per_quarter, item.note_count) for item in selected
        ] + [
            (float(_row_value(row, "density_per_quarter", 0) or 0),
             int(_row_value(row, "note_count", 0) or 0)) for row in rows
        ]
        density_weight = sum(weight for _, weight in density_weighted)
        density = (
            sum(value * weight for value, weight in density_weighted) / density_weight
            if density_weight else 0.0
        )
        cc1_values = ScalarStats.merge(item.cc1.values for item in selected)
        cc11_values = ScalarStats.merge(item.cc11.values for item in selected)
        length = sum(item.length_quarters for item in selected)
        profiles[role] = RoleProfile(
            role=role,
            track_count=len(selected) + len(rows),
            note_count=note_count,
            velocity=velocity,
            duration_quarters=duration,
            timing_offset_quarters=ScalarStats.merge(
                item.timing_offset_quarters for item in selected
            ),
            swing_ratio=ScalarStats.merge(item.swing_ratio for item in selected),
            density_per_quarter=density,
            velocity_by_16th=tuple(
                ScalarStats.merge(item.velocity_by_16th[position] for item in selected)
                for position in range(16)
            ),
            timing_by_16th=tuple(
                ScalarStats.merge(item.timing_by_16th[position] for item in selected)
                for position in range(16)
            ),
            cc1=CCStats(cc1_values, sum(item.cc1.values.count for item in selected) / max(length, 1e-9)),
            cc11=CCStats(cc11_values, sum(item.cc11.values.count for item in selected) / max(length, 1e-9)),
        )
    return profiles


@dataclass(frozen=True)
class NoteTarget:
    velocity: int
    duration_quarters: float
    timing_offset_quarters: float


class GoldDNAModel:
    """A deterministic, role/beat-conditioned performance target model."""

    def __init__(self, profiles: Mapping[str, RoleProfile]):
        self.profiles = dict(sorted(profiles.items()))

    @classmethod
    def fit(
        cls, features: Iterable[TrackFeatures], track_stats: Iterable[Mapping] = ()
    ) -> "GoldDNAModel":
        return cls(aggregate_profiles(features, track_stats))

    @classmethod
    def from_dict(cls, payload: Mapping) -> "GoldDNAModel":
        """Restore a model previously produced by :meth:`to_dict`."""
        def scalar(value):
            return ScalarStats(**value) if isinstance(value, Mapping) else ScalarStats()
        profiles = {}
        for role, value in payload.get("profiles", {}).items():
            profiles[role] = RoleProfile(
                role=value.get("role", role), track_count=int(value.get("track_count", 0)),
                note_count=int(value.get("note_count", 0)), velocity=scalar(value.get("velocity", {})),
                duration_quarters=scalar(value.get("duration_quarters", {})),
                timing_offset_quarters=scalar(value.get("timing_offset_quarters", {})),
                swing_ratio=scalar(value.get("swing_ratio", {})),
                density_per_quarter=float(value.get("density_per_quarter", 0)),
                velocity_by_16th=tuple(scalar(item) for item in value.get("velocity_by_16th", [{}] * 16)),
                timing_by_16th=tuple(scalar(item) for item in value.get("timing_by_16th", [{}] * 16)),
                cc1=CCStats(scalar(value.get("cc1", {}).get("values", {})), float(value.get("cc1", {}).get("changes_per_quarter", 0))),
                cc11=CCStats(scalar(value.get("cc11", {}).get("values", {})), float(value.get("cc11", {}).get("changes_per_quarter", 0))),
            )
        return cls(profiles)

    @classmethod
    def fit_midis(
        cls, midis: Sequence[MidiFile], role_maps: Sequence[RoleMap | None] | None = None,
        track_stats: Iterable[Mapping] = (),
    ) -> "GoldDNAModel":
        maps = role_maps or [None] * len(midis)
        if len(maps) != len(midis):
            raise ValueError("role_maps and midis must have equal length")
        features = [feature for midi, roles in zip(midis, maps) for feature in extract_features(midi, roles)]
        return cls.fit(features, track_stats)

    def transform_note(
        self,
        role: str,
        sixteenth_position: int,
        velocity: int,
        duration_quarters: float,
        *,
        source_velocity_mean: float | None = None,
        source_velocity_std: float | None = None,
        strength: float = 1.0,
    ) -> NoteTarget:
        """Return a repeatable Gold target without random sampling."""

        profile = self.profiles.get(role) or self.profiles.get("melodic")
        if profile is None:
            return NoteTarget(int(velocity), float(duration_quarters), 0.0)
        position = int(sixteenth_position) % 16
        velocity_stats = profile.velocity_by_16th[position]
        if not velocity_stats.count:
            velocity_stats = profile.velocity
        timing_stats = profile.timing_by_16th[position]
        if not timing_stats.count:
            timing_stats = profile.timing_offset_quarters
        source_mean = float(velocity if source_velocity_mean is None else source_velocity_mean)
        source_std = max(1.0, float(source_velocity_std or 1.0))
        z_score = (float(velocity) - source_mean) / source_std
        desired_velocity = velocity_stats.mean + z_score * velocity_stats.std
        desired_duration = (
            profile.duration_quarters.mean
            if profile.duration_quarters.count else float(duration_quarters)
        )
        amount = max(0.0, min(1.0, float(strength)))
        return NoteTarget(
            velocity=max(1, min(127, round(velocity * (1 - amount) + desired_velocity * amount))),
            duration_quarters=max(0.0, duration_quarters * (1 - amount) + desired_duration * amount),
            timing_offset_quarters=timing_stats.mean * amount,
        )

    def to_dict(self) -> dict:
        return {"version": 1, "profiles": {role: asdict(profile) for role, profile in self.profiles.items()}}


def track_feature_to_dict(feature: TrackFeatures) -> dict:
    return asdict(feature)


def track_feature_from_dict(value: Mapping) -> TrackFeatures:
    def scalar(item): return ScalarStats(**item)
    return TrackFeatures(
        track=int(value["track"]), channel=int(value["channel"]), role=str(value["role"]),
        note_count=int(value["note_count"]), length_quarters=float(value["length_quarters"]),
        density_per_quarter=float(value["density_per_quarter"]), velocity=scalar(value["velocity"]),
        duration_quarters=scalar(value["duration_quarters"]),
        timing_offset_quarters=scalar(value["timing_offset_quarters"]), swing_ratio=scalar(value["swing_ratio"]),
        velocity_by_16th=tuple(scalar(item) for item in value["velocity_by_16th"]),
        timing_by_16th=tuple(scalar(item) for item in value["timing_by_16th"]),
        cc1=CCStats(scalar(value["cc1"]["values"]), float(value["cc1"]["changes_per_quarter"])),
        cc11=CCStats(scalar(value["cc11"]["values"]), float(value["cc11"]["changes_per_quarter"])),
        pitch=scalar(value.get("pitch", {})),
        interval_abs=scalar(value.get("interval_abs", {})),
        rest_quarters=scalar(value.get("rest_quarters", {})),
        monophony_ratio=float(value.get("monophony_ratio", 0)),
        overlap_ratio=float(value.get("overlap_ratio", 0)),
        legato_ratio=float(value.get("legato_ratio", 0)),
        step_ratio=float(value.get("step_ratio", 0)),
        leap_ratio=float(value.get("leap_ratio", 0)),
        repeated_note_ratio=float(value.get("repeated_note_ratio", 0)),
        phrase_count=int(value.get("phrase_count", 0)),
        phrase_length_notes=scalar(value.get("phrase_length_notes", {})),
        pitch_bend=CCStats(scalar(value.get("pitch_bend", {}).get("values", {})),
                           float(value.get("pitch_bend", {}).get("changes_per_quarter", 0))),
        pressure=CCStats(scalar(value.get("pressure", {}).get("values", {})),
                         float(value.get("pressure", {}).get("changes_per_quarter", 0))),
    )