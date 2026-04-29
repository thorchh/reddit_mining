# Phase 0 — Pilot Study

Early pilot work (December 2025) that preceded the main pipeline.

## Files

| File | What it was |
|------|-------------|
| `pilot_sycophancy.py` | Initial pilot script exploring sycophancy detection approach |
| `extract_pilot_wrong_answers.py` | Extracted posts with wrong user beliefs from pilot dataset |
| `pilot_candidates.json` | 50 candidate posts selected for pilot annotation (seed=42) |
| `pilot_test_cases.jsonl` | Formatted test cases from pilot selection |
| `pilot_review_summary.md` | Human review summary of pilot results |

## Context

The pilot validated that the r/AskDocs physician-correction framing was a viable signal
for identifying posts where users held wrong beliefs. The screening approach, rubric,
and post selection logic from this phase fed directly into `screen_cases.py` and
`output/screening/screening_final.json` (5,241 screened cases).
