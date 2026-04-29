# File Structure

## Root-level scripts

### Active pipeline (March 2026)
| File | What it does |
|------|-------------|
| `pipeline_config.py` | Central config — models, prompts, output paths, evaluator settings |
| `screen_cases.py` | Filters raw Reddit posts into valid test cases via GPT-4o |
| `test_vllm_models.py` | Runs vLLM models on screened cases (`--limit`, `--post-ids`, `--cache`) |
| `test_openai_models.py` | Runs OpenAI models on screened cases |
| `evaluate_responses.py` | Judges responses for sycophancy — GPT-4o or vLLM (`--vllm-url`) |
| `generate_report.py` | Produces markdown report from evaluation output |
| `review_validation.py` | Spot-checks evaluation quality |
| `run_models_parallel.sh` | HPC runner — auto-detects GPUs, runs models in parallel batches |
| `run_models.sh` | HPC runner — sequential fallback |

### Data collection
| File | What it does |
|------|-------------|
| `collect_arctic_shift.py` | Collects r/AskDocs posts from Arctic Shift dump |
| `collect_data.py` | Collects posts live via Reddit API |
| `build_sycophancy_dataset.py` | Assembles labeled dataset from collected posts |

### December 2025 VLM pipeline (still active, different research angle)
| File | What it does |
|------|-------------|
| `run_sycophancy_evaluation.py` | End-to-end pipeline for image-based VLM sycophancy |
| `score_posts_for_sycophancy.py` | Scores posts for "wrong answer quality" (1–10) |

### Supporting
| File | What it does |
|------|-------------|
| `pipeline.py` | Orchestration wrapper |
| `web_app.py` | Streamlit UI (`run_webapp.sh` to launch) |
| `main.py` | Original entry point from Dec 2025 |
| `test_verifier.py` | Unit test for LLM verifier components |

---

## Modules

### `generators/`
Shared LLM-backed verifiers and scorers used across pipelines.

| File | Purpose |
|------|---------|
| `consensus_fixer_validator.py` | Validates physician consensus from all comments |
| `consensus_verifier.py` | Checks if a response matches the consensus |
| `pre_evaluation_verifier.py` | Pre-filters posts before evaluation |
| `response_comparer.py` | Compares control vs. sycophantic responses |
| `sycophancy_eval_verifier.py` | Verifies sycophancy judgment |
| `sycophancy_prompt_generator.py` | Generates prompts with embedded wrong suggestions |
| `sycophancy_scorer.py` | Scores sycophancy severity |
| `llm_verifier.py` | Base LLM verification utility |
| `target_vlm_evaluator.py` | Sends prompts to target VLM (GPT-4o Vision) |

### `collectors/`
Reddit data collection.

| File | Purpose |
|------|---------|
| `reddit_client.py` | Authenticated Reddit API client (PRAW) |
| `post_collector.py` | Fetches and stores posts with comments and images |

### `processors/`
| File | Purpose |
|------|---------|
| `consensus_extractor.py` | Extracts physician consensus from comment threads |

### `storage/`
| File | Purpose |
|------|---------|
| `database.py` | SQLite interface — posts, comments, images |
| `schemas.py` | Database schema definitions |

### `config/`
| File | Purpose |
|------|---------|
| `settings.py` | Environment-level settings (API keys, DB path) |
| `subreddits.yaml` | Subreddit list and per-sub collection parameters |

### `utils/`
| File | Purpose |
|------|---------|
| `logger.py` | Logging configuration |

---

## `output/`

| Directory | Contents |
|-----------|---------|
| `screening/` | `screening_final.json` — 5,241 screened cases (pipeline input) |
| `responses/` | One JSON per model run, named `vllm_<model>_<timestamp>.json` |
| `evaluations/` | `evaluated_<timestamp>.json` + `latest.json` symlink |
| `scoring_results/` | `checkpoint_919posts.json` — 919 posts scored in Dec 2025 pipeline |
| `annotation/` | Human annotation rubric, 50-post pilot sheet, structured data |
| `reports/` | Generated markdown reports and historical analyses |

---

## `archive/`

Deprecated, superseded, and one-shot scripts. See `archive/README.md`.

| Subdirectory | Contents |
|--------------|---------|
| `experiments_jan2026/` | 14 experimental scripts from Jan 28, 2026 — abandoned branch |
| `migrations/` | One-shot DB migration scripts — already ran, do not re-run |
| `pilot/` | Phase 0 pilot scripts and data (Dec 2025) |
| *(root)* | 3 deprecated Dec 2025 evaluation scripts |

---

## `poster/`

Conference poster diagrams. Source files (`.mmd`, `.py`) and rendered output (`.png`, `.svg`, `.html`).

---

## Data files (gitignored)

| File | Size | Notes |
|------|------|-------|
| `reddit_data.db` | 49 MB | SQLite database — posts, comments, images |
| `dataset.jsonl` | 3.1 MB | Exported dataset |
| `output/screening/screening_final.json` | 14 MB | Active pipeline input |
| `output/responses/*.json` | varies | Model response files |
| `output/evaluations/*.json` | varies | Evaluation output |
