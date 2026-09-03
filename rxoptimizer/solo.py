"""Solo-instrument classification and expressive profile helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .features import TrackFeatures


def instrument_family(program: int | None, role: str) -> str:
    program = int(program or 0)
    if role == "guitar" or 24 <= program <= 31:
        return "guitar_solo"
    ranges = (
        (0, 7, "piano"), (8, 15, "chromatic"), (16, 23, "organ"),
        (40, 47, "strings"), (48, 55, "ensemble"), (56, 63, "brass"),
        (64, 71, "reed"), (72, 79, "pipe"), (80, 87, "synth_lead"),
        (88, 95, "synth_pad"), (104, 111, "ethnic"),
    )
    return next((name for low, high, name in ranges if low <= program <= high), "melodic_solo")


def solo_descriptor(feature: TrackFeatures, program: int | None = None) -> dict:
    """Return an auditable lead/solo likelihood and its musical evidence."""
    eligible = feature.role in ("melodic", "guitar") and feature.note_count >= 8
    pitch_center = feature.pitch.mean if feature.pitch.count else 0
    score = 0.0
    if eligible:
        score += .34 * max(0.0, min(1.0, feature.monophony_ratio))
        score += .14 * min(1.0, feature.pitch_bend.changes_per_quarter * 2)
        score += .08 * min(1.0, feature.pressure.changes_per_quarter * 2)
        score += .10 * min(1.0, feature.cc1.changes_per_quarter * 2)
        score += .08 * min(1.0, feature.cc11.changes_per_quarter * 2)
        score += .08 if pitch_center >= 50 else 0
        score += .08 if feature.phrase_count >= 2 else 0
        score += .05 if .2 <= feature.density_per_quarter <= 8 else 0
        score += .05 if feature.role == "guitar" else 0
    score = round(min(1.0, score), 4)
    return {
        "track": feature.track, "channel": feature.channel, "role": feature.role,
        "program": int(program or 0), "family": instrument_family(program, feature.role),
        "note_count": feature.note_count, "solo_score": score,
        "is_solo_candidate": int(eligible and score >= .62),
        "pitch_mean": pitch_center, "pitch_min": feature.pitch.minimum if feature.pitch.count else 0,
        "pitch_max": feature.pitch.maximum if feature.pitch.count else 0,
        "interval_mean": feature.interval_abs.mean, "monophony_ratio": feature.monophony_ratio,
        "overlap_ratio": feature.overlap_ratio, "legato_ratio": feature.legato_ratio,
        "step_ratio": feature.step_ratio, "leap_ratio": feature.leap_ratio,
        "repeated_note_ratio": feature.repeated_note_ratio, "phrase_count": feature.phrase_count,
        "phrase_length_notes": feature.phrase_length_notes.mean,
        "rest_quarters": feature.rest_quarters.mean,
        "velocity_mean": feature.velocity.mean, "velocity_std": feature.velocity.std,
        "duration_quarters": feature.duration_quarters.mean,
        "pitch_bend_rate": feature.pitch_bend.changes_per_quarter,
        "pitch_bend_range": max(abs(feature.pitch_bend.values.minimum), abs(feature.pitch_bend.values.maximum))
            if feature.pitch_bend.values.count else 0,
        "cc1_rate": feature.cc1.changes_per_quarter, "cc1_mean": feature.cc1.values.mean,
        "cc11_rate": feature.cc11.changes_per_quarter, "cc11_mean": feature.cc11.values.mean,
        "pressure_rate": feature.pressure.changes_per_quarter, "pressure_mean": feature.pressure.values.mean,
    }


MODEL_FIELDS = (
    "monophony_ratio", "overlap_ratio", "legato_ratio", "step_ratio", "leap_ratio",
    "repeated_note_ratio", "phrase_length_notes", "rest_quarters", "velocity_mean",
    "velocity_std", "duration_quarters", "pitch_bend_rate", "pitch_bend_range",
    "cc1_rate", "cc1_mean", "cc11_rate", "cc11_mean", "pressure_rate", "pressure_mean",
)


def aggregate_solo_models(rows: Iterable[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        if row.get("is_solo_candidate"):
            groups[(row["family"], row.get("tempo_bucket", 0), row.get("meter_num", 4), row.get("meter_den", 4))].append(row)
    models = []
    for (family, tempo, meter_num, meter_den), selected in sorted(groups.items()):
        weights = [max(1, int(row["note_count"])) for row in selected]
        weight = sum(weights)
        profile = {field: sum(float(row.get(field, 0)) * w for row, w in zip(selected, weights)) / weight
                   for field in MODEL_FIELDS}
        models.append({"family": family, "tempo_bucket": tempo, "meter_num": meter_num,
                       "meter_den": meter_den, "track_count": len(selected), "note_count": weight,
                       "profile": profile})
    return models


def choose_solo_model(models: Iterable[dict], family: str, tempo_bpm: float | None,
                      meter_num: int = 4, meter_den: int = 4) -> dict | None:
    candidates = [row for row in models if row["family"] == family and
                  int(row.get("meter_num", 4)) == meter_num and int(row.get("meter_den", 4)) == meter_den]
    if not candidates:
        candidates = [row for row in models if row["family"] in (family, "melodic_solo")]
    if not candidates:
        return None
    target = round(float(tempo_bpm or 0) / 20) * 20 if tempo_bpm else 0
    return min(candidates, key=lambda row: abs(int(row.get("tempo_bucket", 0)) - target))