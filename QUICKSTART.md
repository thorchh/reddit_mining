# Quickstart — Onboarding Guide

A 10-minute orientation for picking up this repo.

## What this project is

Tests whether empathy-priming system prompts cause LLMs to be sycophantic in
medical contexts (i.e., agree with a user's wrong belief instead of correcting it).

Inputs: 5,241 r/AskDocs posts where a physician explicitly corrected a wrong belief.
Outputs: per-model sycophancy rates under a `baseline` vs `empathy_first` system prompt.

## Read in this order

1. **`README.md`** — pipeline diagram, quick-start commands, models tested, sample prompts.
2. **`pipeline_config.py`** — single source of truth: every model, prompt, path, and evaluator setting.
3. **`docs/FILE_STRUCTURE.md`** — every folder and file explained.
4. **`docs/SCORING_APPROACH.md`** + **`docs/LLM_VERIFIER_GUIDE.md`** — methodology details.

That's enough to understand the project. Trace one full run end-to-end after that.

## Trace a run end-to-end

```
screen_cases.py        →  output/screening/screening_final.json   (5,241 cases — already done)
test_vllm_models.py    →  output/responses/vllm_<model>_<ts>.json (one per model)
evaluate_responses.py  →  output/evaluations/evaluated_<ts>.json
generate_report.py     →  output/reports/<ts>.md
```

Run the smallest possible version locally:

```bash
uv pip install -r requirements.txt
export OPENAI_API_KEY=...
python pipeline/test_openai_models.py --limit 5
python pipeline/evaluate_responses.py --input output/responses/<file>.json
```

## Mental model of the directory tree

| Folder | Active? | What it is |
|--------|---------|-----------|
| `pipeline/` | yes | Active pipeline scripts (March 2026) |
| `pipeline_config.py` | yes | Central config |
| `collection/` | yes | Fresh data collection (Arctic Shift / Reddit API) |
| `webapp/` | yes | Streamlit UI for browsing results |
| `collectors/`, `processors/`, `storage/`, `config/`, `utils/` | yes | Supporting modules |
| `output/` | yes | Generated artifacts (screening, responses, evaluations, reports) |
| `poster/` | yes | Conference poster diagrams |
| `archive/` | **no** | Everything legacy — Dec 2025 VLM pipeline, Jan 2026 experiments, deprecated scripts, and `legacy_generators/` (the old LLM verifier modules). Don't run anything here. |

## What's NOT here that you might expect

- `generators/` used to live at the root — it has been moved to `archive/legacy_generators/` because the active pipeline does not import any of it. All those modules powered the old "Stage 1: generate prompt → Stage 2: hit target VLM → Stage 3: verify" pipeline, which the current approach replaced.
- The active pipeline uses real physician corrections from Reddit directly, so there is no test-case generation step anymore.

## Where data lives

- `reddit_data.db` (49 MB SQLite, gitignored) — raw posts, comments, images
- `output/screening/screening_final.json` (14 MB, gitignored) — the 5,241 screened cases used as pipeline input
- All model output, evaluations, and reports go under `output/`

## HPC notes

- Cluster path: `/project2/swabhas_1625/thorchri/reddit_mining/`
- Venv: `../vllm_env`, Python module `3.11.9`
- Use `srun` (not `salloc`); partition `nlp_hiprio`, account `swabhas_1625`
- Entry point: `bash run_models_parallel.sh` (adaptive GPU batching)
