# Experiments — January 28, 2026

One-day exploratory burst before the structured pipeline was built. None of these scripts
were carried forward; they were superseded by the Phase 5 pipeline (March 2026).

## Files

| File | What it was |
|------|-------------|
| `test_sycophancy_multimodel.py` | Multi-model sycophancy test runner (iterative, parallelized during this session) |
| `test_sycophancy_clean.py` | Cleaned-up version of multimodel runner |
| `test_sycophancy_targeted.py` | Targeted sycophancy tests on specific post types |
| `test_sycophancy_v2.py` | Second iteration of sycophancy test harness |
| `test_large_scale_sycophancy.py` | Attempted large-scale run |
| `test_reddit_diversity.py` | Reddit post diversity exploration |
| `test_system_prompts_large.py` | System prompt variation experiments |
| `sycophancy_research.py` | Umbrella research script used during exploration |
| `collect_large_dataset.py` | Data collection attempt (superseded by `collect_arctic_shift.py`) |
| `collect_text_sycophancy.py` | Text-only sycophancy data collector |
| `score_text_sycophancy.py` | Scorer for text-only branch |
| `test_text_sycophancy.py` | Tests for text-only branch |
| `multiturn_sycophancy.py` | Multi-turn conversation sycophancy variant |
| `reversal_sycophancy.py` | Reversal/flip sycophancy variant |
| `12-cases.txt` | 12 hand-selected reference cases used during debugging |

## Why archived

The structured pipeline introduced in March 2026 (`screen_cases.py` → `run_models_parallel.sh` →
`evaluate_responses.py` → `generate_report.py`) replaced all of these. The text-only and
multi-turn branches were not pursued further.

See the main `archive/README.md` for overall archive context.
