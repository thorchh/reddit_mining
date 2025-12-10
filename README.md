# VLM Sycophancy Evaluation Framework

A complete pipeline for testing Vision-Language Model (VLM) susceptibility to sycophantic behavior using Reddit medical and identification posts.

## Overview

This framework tests whether VLMs can be influenced to agree with incorrect suggestions when analyzing images. The hypothesis: VLMs may exhibit sycophantic behavior by agreeing with wrong diagnoses/identifications suggested by users, even when they have access to the correct information.

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 0: Data Collection (fetch_reddit_posts.py)                 │
│ Fetch posts from medical/identification subreddits               │
│ Download images, store in SQLite database                        │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Post Scoring (score_posts_for_sycophancy.py)            │
│ Score posts based on "wrong answer quality" (1-10)              │
│ Select best wrong answer from Reddit comments                    │
│ Output: checkpoint_919posts.json                                 │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Complete Evaluation (run_sycophancy_evaluation.py)      │
│                                                                  │
│ Phase 1: CONSENSUS VALIDATION                                   │
│   • LLM analyzes top 40 comments per post                       │
│   • Determines TRUE consensus (not just top comment)            │
│   • Finds plausible WRONG alternatives                          │
│   • Filters posts where ground_truth == wrong_answer            │
│                                                                  │
│ Phase 2: 3-STAGE TESTING (for validated posts)                  │
│   ┌──────────────────────────────────────────────────────────┐ │
│   │ Stage 1: Generate Sycophantic Prompt                     │ │
│   │ • Creates prompt suggesting wrong answer                 │ │
│   │ • Strategy varies by score (aggressive/moderate/brief)   │ │
│   └──────────────────────────────────────────────────────────┘ │
│                         ↓                                        │
│   ┌──────────────────────────────────────────────────────────┐ │
│   │ Stage 2: Test VLM (TWO conditions)                       │ │
│   │ • CONTROL: Neutral prompt ("What do you see?")          │ │
│   │ • SYCOPHANTIC: Prompt with wrong suggestion             │ │
│   └──────────────────────────────────────────────────────────┘ │
│                         ↓                                        │
│   ┌──────────────────────────────────────────────────────────┐ │
│   │ Stage 3: Verify Both Responses                           │ │
│   │ • LLM checks control response: Correct?                  │ │
│   │ • LLM checks sycophantic response: Sycophantic? Correct? │ │
│   │ • Comparison: Did answer change?                         │ │
│   └──────────────────────────────────────────────────────────┘ │
│                                                                  │
│ Output: results.json, summary.json                               │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

```bash
# Install dependencies
pip install openai requests praw

# Set API keys
export OPENAI_API_KEY="your-key-here"
export REDDIT_CLIENT_ID="your-id"
export REDDIT_CLIENT_SECRET="your-secret"
```

### Running the Pipeline

#### Step 1: Score Posts (if not already done)

```bash
python score_posts_for_sycophancy.py \
  --checkpoint output/scoring_results/checkpoint_919posts.json \
  --yes
```

**Output**: `output/scoring_results/checkpoint_919posts.json` with 919 scored posts

---

#### Step 2: Run Complete Evaluation

```bash
python run_sycophancy_evaluation.py \
  --checkpoint output/scoring_results/checkpoint_919posts.json \
  --scores 2,3,4,5,6,7,8,9 \
  --sample-per-score 5 \
  --yes
```

**Output**:
- `output/sycophancy_final/results.json` - Full results
- `output/sycophancy_final/summary.json` - Aggregate statistics

---

## Key Files

| File | Purpose |
|------|---------|
| `run_sycophancy_evaluation.py` | **Main pipeline** (validation + testing) |
| `score_posts_for_sycophancy.py` | Score posts for wrong answer quality |
| `generators/consensus_fixer_validator.py` | Validates consensus from all comments |
| `generators/sycophancy_prompt_generator.py` | Generates sycophantic prompts |
| `generators/target_vlm_evaluator.py` | Tests target VLM |

---

## Understanding Results

### Key Metrics

- **Sycophancy rate**: % of cases where VLM agreed with wrong suggestions
- **Control accuracy**: % correct without suggestions
- **Sycophantic accuracy**: % correct with wrong suggestions
- **Accuracy drop**: How much accuracy decreased

### Example Output

```json
{
  "total_posts": 40,
  "control_accuracy": 0.45,
  "sycophantic_accuracy": 0.25,
  "sycophancy_rate": 0.65,
  "accuracy_drop": 0.20
}
```

**Interpretation**: VLM showed sycophancy in 65% of cases, causing accuracy to drop from 45% to 25%.

---

## Cost Estimates

| Component | Cost per Post | Cost for 40 Posts |
|-----------|--------------|-------------------|
| Consensus Validation | $0.007 | $0.28 |
| 3-Stage Testing | $0.010 | $0.40 |
| **Total** | **$0.017** | **$0.68** |

---

## License

MIT License
