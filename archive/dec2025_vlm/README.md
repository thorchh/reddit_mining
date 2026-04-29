# December 2025 — VLM Vision Pipeline

Original sycophancy pipeline (Dec 2025) that tested Vision-Language Models on image-based
medical posts. This approach was superseded by the March 2026 text-LLM pipeline.

## What it did

Tested whether VLMs (GPT-4o Vision) could be influenced to agree with wrong diagnoses
when images were paired with a sycophantic prompt suggesting an incorrect answer.

## Files

| File | Purpose |
|------|---------|
| `main.py` | Original entry point (Phase 1: collect posts from subreddits) |
| `pipeline.py` | Full orchestration wrapper |
| `score_posts_for_sycophancy.py` | Scored posts for "wrong answer quality" (1–10 scale) |
| `build_sycophancy_dataset.py` | Assembled labeled dataset from scored posts |
| `run_sycophancy_evaluation.py` | Main 3-stage evaluation: consensus validation → prompt generation → VLM test |

## Why superseded

The VLM image approach had high per-post cost (image tokens) and mixed results.
The March 2026 pipeline pivots to text-only LLMs on r/AskDocs correction posts,
which gives a cleaner experimental design (no image quality confounds) and allows
testing open-source models at scale via vLLM on HPC.

The `generators/` module (consensus_fixer_validator, sycophancy_prompt_generator, etc.)
was built for this pipeline and is still present in the active codebase.
