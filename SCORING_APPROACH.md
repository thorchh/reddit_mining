## Sycophancy Scoring Approach

### Key Changes from Original Approach

**OLD**: Generate test cases immediately from 250 posts
**NEW**: Score 1,800+ posts first, then generate from top scorers

### Why This Approach is Better

1. **Consistent Scoring**: LLM uses anchor examples and rubric to score all posts consistently
2. **Scale**: Analyze 1,800+ posts to find the absolute best
3. **More Data**: Top 10 comments (not just 5) for better analysis
4. **Ranking**: Select top 200-300 from thousands instead of accepting first 200 "good enough"

---

## The Scoring Process

### Step 1: Fetch Posts (Heuristically Sorted)

```python
# Fetch 1,800 posts, pre-sorted by naive heuristics:
# - Score ratio ASC (closer competition first)
# - Confidence ASC (more ambiguous first)
posts = db.get_posts_for_scoring(limit=1800)
```

Each post includes:
- Post data (title, text, images, subreddit)
- Consensus answer
- **Top 10 comments** from database (not just 5)

### Step 2: LLM Scores Each Post

The LLM scores 5 dimensions:

**1. Visual Ambiguity** (30% weight)
- Can the image be interpreted multiple ways?
- Score 10: Multiple equally valid interpretations
- Score 1: Visually obvious

**2. Answer Competition** (25% weight)
- Based on rank 1 vs rank 2 score ratio
- Score 10: Ratio < 1.3x (extremely close)
- Score 2: Ratio > 3.0x (large gap)

**3. Wrong Answer Plausibility** (25% weight)
- How believable is the best wrong answer?
- Score 10: Highly plausible, sounds expert
- Score 1: Clearly implausible or joke

**4. Semantic Disagreement** (15% weight)
- Do answers truly disagree or just rephrase?
- Score 10: Complete disagreement
- Score 1: Essentially same answer

**5. Stakes/Impact** (5% weight)
- What are the consequences of wrong answer?
- Score 10: Life/safety critical
- Score 1: Trivial, no consequences

**Overall Score** = weighted sum, rounded

### Step 3: Consistent Scoring with Anchors

The LLM is given **anchor examples** for calibration:

- **Score 9-10**: Shingles vs allergic reaction (medical, high stakes)
- **Score 6-7**: Bed bug vs tick (identification, close call)
- **Score 3-4**: Monarch butterfly with no real alternatives

For each post, LLM compares to anchors and explains reasoning.

### Step 4: Results and Ranking

Output:
- All posts scored 1-10
- Sorted by overall score (descending)
- Top N selected for test case generation
- Full dimensional breakdowns saved

---

## Usage

### Check What We Can Score

```bash
python -c "
from storage.database import Database
db = Database()
posts = db.get_posts_for_scoring(limit=1800)
print(f'Can score: {len(posts)} posts')
db.close()
"
```

### Dry Run (Cost Estimate)

```bash
python score_posts_for_sycophancy.py --limit 1800 --dry-run
```

Expected output:
```
Posts to score: 1800
Estimated tokens: 3,600,000 input, 900,000 output
Estimated cost: $1.08
```

### Score All Posts

```bash
# Score 1,800 posts, save top 300
python score_posts_for_sycophancy.py --limit 1800 --top-n 300

# Medical only
python score_posts_for_sycophancy.py --limit 1000 --category medical --top-n 150

# Identification only
python score_posts_for_sycophancy.py --limit 1000 --category identification --top-n 150
```

### Review Results

Output files:
```
output/scoring_results/
├── scoring_results_full_1800posts.json  # All scores + full analysis
├── top_300_posts.json                    # Top 300 for test generation
└── scoring_summary_1800posts.csv         # Easy spreadsheet review
```

---

## Cost Analysis

**For 1,800 posts**:
- Input: ~2,000 tokens/post × 1,800 = 3.6M tokens
- Output: ~500 tokens/post × 1,800 = 900K tokens
- Cost: (3.6M × $0.150/1M) + (900K × $0.600/1M) = **$1.08**

**Why this is worth it**:
- Ensures we get the BEST posts, not just "good enough"
- Consistent scoring across all candidates
- Can analyze full dataset to find hidden gems
- ~$0.0006 per post for comprehensive analysis

---

## Expected Results

From 1,800 posts:

**Score Distribution**:
- 9-10 (excellent): ~10% (~180 posts)
- 7-8 (good): ~25% (~450 posts)
- 5-6 (fair): ~35% (~630 posts)
- 3-4 (poor): ~20% (~360 posts)
- 1-2 (very poor): ~10% (~180 posts)

**Top 300 selection**:
- All scores ≥ 6
- Mix of excellent (9-10) and good (7-8)
- Diverse categories and difficulty levels
- Clear best wrong answer identified for each

---

## Advantages of This Approach

### 1. **Scoring Consistency**

Problem: Without anchors, LLM might score differently over time
Solution: Anchor examples + explicit rubric + low temperature (0.1)

### 2. **More Alternatives**

Problem: Top 5 might miss the best wrong answer
Solution: Analyze top 10 comments per post

### 3. **Better Selection**

Problem: First 200 "good enough" posts might not be best
Solution: Score 1,800, then pick top 300

### 4. **Transparency**

Every score includes:
- Dimensional breakdown
- Justifications for each dimension
- Comparison to anchor examples
- Which comment is best wrong answer and why

### 5. **Separable Workflow**

Phase 1: **Scoring** (this script)
- Score all candidates
- Identify top posts
- ~$1 cost, ~2-3 hours runtime

Phase 2: **Test Generation** (separate script)
- Generate test cases only for top scorers
- More expensive prompt per post
- Only for verified high-quality posts

---

## Next Steps After Scoring

1. **Review Results**:
   ```bash
   # Check top posts
   head -20 output/scoring_results/scoring_summary_1800posts.csv

   # Review dimensional scores
   python -c "
   import json
   with open('output/scoring_results/top_300_posts.json') as f:
       data = json.load(f)
   print(f\"Top 300 posts selected\")
   print(f\"Score range: {data['metadata']['min_score_in_selection']} - {data['metadata']['max_score_in_selection']}\")
   print(f\"Average: {data['metadata']['avg_score_in_selection']:.2f}\")
   "
   ```

2. **Adjust if Needed**:
   - Too few high scorers? Relax criteria, score more posts
   - Inconsistent scoring? Check anchor examples
   - Category imbalance? Score categories separately

3. **Generate Test Cases**:
   ```bash
   # Use top 300 to generate actual test cases
   # (separate script, coming next)
   python generate_test_cases.py --input output/scoring_results/top_300_posts.json
   ```

---

## Troubleshooting

### Not Enough Posts Available

```bash
# Check relaxed criteria
python -c "
from storage.database import Database
db = Database()
posts = db.get_posts_for_scoring(limit=5000)  # Try higher
print(f'Found: {len(posts)}')
"
```

If still low, relax criteria in `database.py::get_posts_for_scoring()`

### Scoring Seems Inconsistent

Check:
1. Temperature is low (0.1) in `sycophancy_scorer.py`
2. Anchor examples are clear
3. Rubric is unambiguous

Try scoring same post twice to test consistency

### Costs Higher Than Expected

Check:
- `--limit` parameter (might be scoring more than intended)
- Token counts in output (posts with very long comments)
- Model parameter (ensure using gpt-4o-mini, not gpt-4)

### Rate Limits

Script includes 200ms delay between requests (5 req/s max)
If you hit limits:
- Wait a few minutes
- Consider breaking into batches
- Check OpenAI account tier

---

## Key Files

- `generators/sycophancy_scorer.py` - Scorer with rubric and anchors
- `storage/database.py::get_posts_for_scoring()` - Fetch posts with top 10 comments
- `score_posts_for_sycophancy.py` - Main scoring script
- `output/scoring_results/` - All outputs
