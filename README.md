# GM → RX MIDI Optimizer

Production-oriented toolkit for analysing and optimizing General MIDI arrangements for Roland/Korg RX workflows. The repository contains the existing optimizer engines, DNA/evidence models, MIDI corpus, SQLite support, hardware-test material and regression tests.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest
python app.py --help
```

The package is also installable in editable mode:

```bash
python -m pip install -e .
gm-rx-optimizer --help
```

## Project layout

- `app.py` — CLI and application entrypoint
- `rxoptimizer/` — MIDI, rhythm, DNA, evidence, database and optimization engines
- `tests/` — regression and contract tests
- `analysis/` — generated audit and data-quality reports
- `hardware-tests/` and `reference/` — device validation guides and references
- `prism-uploads/` — supplied MIDI corpus and upgrade roadmap

## Upgrade baseline

The upgrade preserves the original architecture and data meaning. New packaging metadata, a reproducible development setup, test discovery configuration and repository hygiene are now included so the project can be installed, tested and extended safely. Database migrations and engine changes should remain backward-compatible and be covered by tests before deployment.

## Safety

Never overwrite the source corpus or production databases during experiments. Use a copy or a dedicated output path, and validate exported MIDI files before loading them onto hardware.
