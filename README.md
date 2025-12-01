# Reddit Mining Pipeline for VLM Sycophancy Research

A data collection pipeline to mine Reddit posts from medical and identification subreddits, extracting "ground truth" consensus answers from community responses to evaluate sycophancy in multimodal LLMs.

## Research Hypothesis

Multimodal LLMs/VLMs are more sycophantic than text-only LLMs because image understanding is "not completely tethered correctly."

## Features

- Collects posts with images from medical and identification subreddits
- Extracts consensus answers from comment upvotes
- Rate limiting and error handling for Reddit API
- SQLite database storage
- Export to JSONL for model evaluation
- Configurable collection targets and filters

## Installation

1. Clone the repository and navigate to the project directory:
```bash
cd reddit_mining
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Reddit API credentials:
   - Go to https://www.reddit.com/prefs/apps
   - Create a new application (script type)
   - Copy `.env.example` to `.env`
   - Fill in your credentials in `.env`

```bash
cp .env.example .env
# Edit .env with your credentials
```

## Usage

### 1. Collect Data from Reddit

Run the main collection script:

```bash
# Test mode (collect from one subreddit only)
python main.py --test

# Collect from all subreddits (150 posts each)
python main.py

# Collect from specific categories
python main.py --categories medical
python main.py --categories identification

# Custom limit per subreddit
python main.py --limit 200

# Collect posts without requiring images
python main.py --no-images
```

### 2. Extract Consensus & Export Dataset

After collecting data, extract consensus answers:

```bash
# Extract consensus and export dataset
python extract_consensus.py

# Export with custom confidence threshold
python extract_consensus.py --min-confidence 0.6

# Export to custom path
python extract_consensus.py --export my_dataset.jsonl

# Extract for specific subreddit only
python extract_consensus.py --subreddit whatisthisthing
```

### 3. View Statistics

Check collection statistics directly from the database:

```bash
python -c "from storage.database import Database; db = Database(); print(db.get_statistics())"
```

## Configuration

### Subreddits

Edit `config/subreddits.yaml` to add or remove subreddits:

```yaml
medical:
  - name: AskDocs
    description: Medical advice with symptom images
    allow_nsfw: true

identification:
  - name: whatisthisthing
    description: General object identification
    allow_nsfw: false
```

### Settings

Adjust collection settings in `.env`:

```bash
# Collection criteria
MIN_COMMENTS=5
MIN_POST_SCORE=10
MAX_POST_AGE_DAYS=365
POSTS_PER_SUBREDDIT=150

# Rate limiting
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_PERIOD=60
```

## Project Structure

```
reddit_mining/
├── config/
│   ├── settings.py          # Environment variables, API limits
│   └── subreddits.yaml      # Subreddit configurations
├── collectors/
│   ├── reddit_client.py     # PRAW wrapper with rate limiting
│   └── post_collector.py    # Main collection logic
├── processors/
│   ├── consensus_extractor.py # Ground truth extraction
│   └── data_cleaner.py      # Filtering and deduplication
├── storage/
│   ├── database.py          # SQLite operations
│   └── schemas.py           # Data models
├── utils/
│   └── logger.py            # Logging configuration
├── main.py                  # Collection orchestration
├── extract_consensus.py     # Consensus extraction script
└── requirements.txt
```

## Database Schema

### Posts Table
- `id`: Reddit post ID
- `subreddit`: Subreddit name
- `title`: Post title
- `selftext`: Post body text
- `author`: Username
- `score`: Upvotes
- `num_comments`: Comment count
- `created_utc`: Timestamp
- `permalink`: Reddit URL
- `url`: Post URL
- `is_nsfw`: NSFW flag
- `has_images`: Boolean
- `image_urls`: JSON array of image URLs

### Comments Table
- `id`: Reddit comment ID
- `post_id`: Parent post ID
- `parent_id`: Parent comment ID (NULL for top-level)
- `author`: Username
- `body`: Comment text
- `score`: Upvotes
- `depth`: Comment depth in tree (0 = top-level)

### Consensus Table
- `post_id`: Associated post
- `consensus_answer`: Top-voted answer
- `confidence_score`: 0-1 confidence score
- `top_answers`: JSON array of top 3-5 answers

## Dataset Format

Exported JSONL format for model evaluation:

```json
{
  "post_id": "abc123",
  "subreddit": "whatisthisthing",
  "question": "What is this weird tool?",
  "context": "Found in my grandpa's garage...",
  "image_urls": ["https://i.redd.it/..."],
  "is_nsfw": false,
  "consensus_answer": "It's a vintage widget wrench",
  "confidence": 0.85,
  "alternative_answers": [...]
}
```

## Target Subreddits

**Medical:**
- r/AskDocs
- r/DermatologyQuestions
- r/medical_advice
- r/DiagnoseMe

**Identification:**
- r/whatisthisthing
- r/whatsthisbug
- r/whatsthisplant
- r/whatsthisbird

## Consensus Algorithm

Simple upvote-based ranking:
1. Extract top-level comments (direct replies to post)
2. Sort by upvotes (comment.score)
3. Top comment = consensus answer
4. Confidence score based on vote ratio:
   - High confidence: top > 2× second place
   - Medium: top > 1.5× second place
   - Low: competitive scores

## Next Steps

After collecting the dataset:
1. Design VLM evaluation prompts (e.g., "User says it's X, what do you think?")
2. Test multiple VLMs (GPT-4V, Claude 3, Gemini Vision)
3. Measure sycophancy: How often do models agree with incorrect user framing vs ground truth?
4. Compare VLM sycophancy rates to text-only LLM baselines

## Troubleshooting

**Authentication Error:**
- Verify credentials in `.env` are correct
- Check Reddit app is configured as "script" type
- Ensure username/password are for the account that created the app

**Rate Limiting:**
- Pipeline includes automatic rate limiting (60 req/min)
- If you still hit limits, increase `RATE_LIMIT_PERIOD` in `.env`

**No Images Found:**
- Some subreddits have fewer image posts
- Try reducing `MIN_POST_SCORE` or `MIN_COMMENTS` in settings
- Use `--no-images` flag to test collection without image requirement

## License

MIT License - See LICENSE file for details

## Citation

If you use this pipeline in your research, please cite:

```
@misc{reddit_vlm_sycophancy,
  title={Reddit Mining Pipeline for VLM Sycophancy Research},
  year={2025}
}
```
