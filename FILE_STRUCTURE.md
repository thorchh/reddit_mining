# File Structure & Component Guide

## Directory Layout

```
reddit_mining/
├── README.md                           # Main documentation
├── FILE_STRUCTURE.md                   # This file
│
├── run_sycophancy_evaluation.py        # ⭐ MAIN SCRIPT - Complete pipeline
├── score_posts_for_sycophancy.py       # Step 1: Score posts
│
├── generators/                         # Core components
│   ├── __init__.py
│   ├── consensus_fixer_validator.py    # Validates consensus from comments
│   ├── sycophancy_prompt_generator.py  # Generates sycophantic prompts
│   ├── target_vlm_evaluator.py         # Tests VLM with prompts
│   ├── consensus_verifier.py           # Verifies response correctness
│   └── response_comparer.py            # Compares control vs sycophantic
│
├── storage/                            # Database layer
│   ├── database.py                     # SQLite database interface
│   └── schema.sql                      # Database schema
│
├── utils/                              # Utilities
│   └── logger.py                       # Logging configuration
│
├── output/                             # Results directory
│   ├── scoring_results/
│   │   └── checkpoint_919posts.json    # Scored posts
│   └── sycophancy_final/
│       ├── results.json                # Full evaluation results
│       └── summary.json                # Aggregate statistics
│
└── reddit_posts.db                     # SQLite database (images + comments)
```

## Component Details

### Main Pipeline Scripts

#### `run_sycophancy_evaluation.py` ⭐
**The main script - use this one!**

```python
# What it does:
# 1. Validates consensus by analyzing all comments
# 2. Runs 3-stage testing (control + sycophantic)
# 3. Generates comprehensive results

# Usage:
python run_sycophancy_evaluation.py \
  --checkpoint output/scoring_results/checkpoint_919posts.json \
  --scores 2,3,4,5,6,7,8,9 \
  --sample-per-score 5 \
  --yes

# Output:
# - output/sycophancy_final/results.json
# - output/sycophancy_final/summary.json
```

#### `score_posts_for_sycophancy.py`
**Pre-processing: Score posts for wrong answer quality**

```python
# What it does:
# - Analyzes Reddit comments to find "wrong answers"
# - Scores based on plausibility, specificity, upvotes
# - Creates checkpoint file for evaluation

# Usage:
python score_posts_for_sycophancy.py \
  --checkpoint output/scoring_results/checkpoint_919posts.json \
  --yes

# Output:
# - checkpoint_919posts.json (919 scored posts)
```

---

### Generator Components

#### `consensus_fixer_validator.py`
**Validates consensus before testing**

```python
from generators.consensus_fixer_validator import ConsensusFixerValidator

validator = ConsensusFixerValidator()

# Analyzes top 40 comments to determine:
# - Is there clear consensus?
# - What is the TRUE consensus answer?
# - Are there plausible wrong alternatives?
# - Are answers semantically different?

result = validator.validate(post_data, all_comments)
# Returns: {"recommendation": "USE|SKIP", "consensus_answer": "...", ...}
```

**Key feature**: Looks at ALL comments, not just top comment

---

#### `sycophancy_prompt_generator.py`
**Generates prompts with wrong suggestions**

```python
from generators.sycophancy_prompt_generator import SycophancyPromptGenerator

generator = SycophancyPromptGenerator()

# Creates realistic prompt suggesting wrong answer
# Strategy varies by score:
# - Score 7-9: "aggressive" (I'm confident it's X)
# - Score 4-6: "moderate" (I think it might be X)
# - Score 2-3: "brief" (Could this be X?)

result = generator.generate_prompt(post_data)
# Returns: {"sycophantic_prompt": "...", "strategy": "aggressive"}
```

---

#### `target_vlm_evaluator.py`
**Tests target VLM**

```python
from generators.target_vlm_evaluator import TargetVLMEvaluator

evaluator = TargetVLMEvaluator()

# Sends prompt + images to VLM
# Currently uses GPT-4o Vision
# Can be modified to test other VLMs

result = evaluator.evaluate(prompt, image_urls)
# Returns: {"vlm_response": "..."}
```

---

#### `consensus_verifier.py`
**Verifies if VLM responses are correct**

```python
from generators.consensus_verifier import ConsensusVerifier

verifier = ConsensusVerifier()

# Checks if VLM response matches ground truth
# Handles semantic similarity (e.g., "ringworm" = "tinea")

result = verifier.verify(post_data, vlm_response)
# Returns: {"verdict": "CORRECT|INCORRECT|PARTIAL"}
```

---

## Deprecated Files (Don't Use)

| File | Status | Replacement |
|------|--------|-------------|
| `evaluate_sycophancy.py` | ❌ Deprecated | Use `run_sycophancy_evaluation.py` |
| `evaluate_sycophancy_enhanced.py` | ❌ Deprecated | Use `run_sycophancy_evaluation.py` |
| `analyze_sycophancy_results.py` | ⚠️ Legacy | For post-hoc analysis only |

---

## Data Flow

```
1. Reddit Data
   ↓
   reddit_posts.db (SQLite)
   ├── posts table (title, images, subreddit)
   ├── comments table (body, score, author)
   └── images table (image URLs, local paths)

2. Scoring
   ↓
   checkpoint_919posts.json
   {
     "results": [
       {
         "post_id": "...",
         "overall_score": 9,
         "best_wrong_answer": {...}
       }
     ]
   }

3. Evaluation
   ↓
   results.json
   {
     "post_id": "...",
     "ground_truth": "melanoma",
     "wrong_answer": "BCC",
     "stage2_vlm_testing": {
       "control": {...},
       "sycophantic": {...}
     },
     "stage3_verification": {...}
   }

4. Summary
   ↓
   summary.json
   {
     "control_accuracy": 0.45,
     "sycophantic_accuracy": 0.25,
     "sycophancy_rate": 0.65
   }
```

---

## Quick Reference

### To run complete evaluation:
```bash
python run_sycophancy_evaluation.py \
  --checkpoint output/scoring_results/checkpoint_919posts.json \
  --scores 2,3,4,5,6,7,8,9 \
  --sample-per-score 5 \
  --yes
```

### To test just a few posts:
```bash
python run_sycophancy_evaluation.py \
  --checkpoint output/scoring_results/checkpoint_919posts.json \
  --scores 9,8 \
  --sample-per-score 2 \
  --yes
```

### To check results:
```bash
cat output/sycophancy_final/summary.json | python -m json.tool
```

---

## Common Tasks

### Change target VLM
Edit `generators/target_vlm_evaluator.py`:
```python
self.model = "gpt-4o"  # Change to your preferred model
```

### Adjust scoring weights
Edit `generators/sycophancy_scorer.py`:
```python
weights = {
    'plausibility': 0.4,
    'specificity': 0.3,
    ...
}
```

### Add more subreddits
Edit `fetch_reddit_posts.py`:
```python
MEDICAL_SUBS = ['AskDocs', 'DermatologyQuestions', ...]
```
