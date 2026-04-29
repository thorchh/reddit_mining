# Archive

Deprecated, superseded, and one-shot scripts kept for historical reference.
Nothing here is part of the active pipeline — see the root `README.md` for current workflow.

## Structure

```
archive/
  experiments_jan2026/   One-day exploratory burst (Jan 28, 2026). Superseded by March pipeline.
  migrations/            One-shot DB migration scripts. Already ran, do not re-run.
  pilot/                 Phase 0 pilot study scripts and data (Dec 2025).
  evaluate_sycophancy.py           Deprecated Dec 10, 2025
  evaluate_sycophancy_enhanced.py  Deprecated Dec 10, 2025
  analyze_sycophancy_results.py    Deprecated Dec 10, 2025
```

## Deprecated Scripts (root of archive/)

### `evaluate_sycophancy.py`
**Deprecated**: Dec 10, 2025 — Used top comment as ground truth without consensus validation.
**Replaced by**: `run_sycophancy_evaluation.py`

### `evaluate_sycophancy_enhanced.py`
**Deprecated**: Dec 10, 2025 — Added pre-evaluation verification but was overly complex.
**Replaced by**: `run_sycophancy_evaluation.py`

### `analyze_sycophancy_results.py`
**Deprecated**: Dec 10, 2025 — Post-hoc analysis designed for old pipeline outputs.
**Replaced by**: `generate_report.py` + `review_validation.py`

## Why the originals were replaced

The old scripts (Dec 2025) had two core problems:
1. **No consensus validation** — top comment used as ground truth without checking it was actually the physician consensus
2. **No control condition** — no neutral prompt baseline meant we couldn't isolate the empathy effect

The current pipeline validates consensus with an LLM before testing, runs both control and sycophantic prompts, and uses vLLM for local model inference on the HPC cluster.
