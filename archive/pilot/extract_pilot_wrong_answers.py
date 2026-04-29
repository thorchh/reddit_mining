#!/usr/bin/env python3
"""
Phase 0: Extract wrong answers from pilot candidates

For each pilot post, extract wrong answers from:
1. Alternative consensus answers (ranks 2-5)
2. Downvoted/low-scored comments
3. VLM-generated (skip for pilot)

Create sample test cases in final JSON format.
"""

import json
from datetime import datetime
from typing import List, Dict, Any
from storage.database import Database
from utils.logger import setup_logger

logger = setup_logger('extract_pilot_wrong_answers')


def dedupe_candidates(candidates: List[Dict]) -> List[Dict]:
    """Remove duplicate posts from candidates."""
    seen = set()
    unique = []
    for c in candidates:
        if c['post_id'] not in seen:
            seen.add(c['post_id'])
            unique.append(c)
    return unique


def extract_alternative_answers(candidate: Dict) -> List[Dict]:
    """Extract wrong answers from alternative consensus answers (ranks 2-5)."""
    wrong_answers = []

    # Skip rank 1 (correct answer), use ranks 2-5 as wrong answers
    for alt in candidate['top_answers'][1:]:  # Skip first (rank 1)
        wrong_answers.append({
            'source_type': 'alternative_rank',
            'source_id': alt['comment_id'],
            'user_suggestion': alt['answer'][:200],  # Truncate for user suggestion
            'original_score': alt['score'],
            'alternative_rank': alt['rank'],
            'author': alt['author']
        })

    return wrong_answers


def extract_downvoted_comments(db: Database, post_id: str) -> List[Dict]:
    """Extract wrong answers from downvoted/low-scored comments."""
    cursor = db.conn.cursor()

    # Get comments with score <= 5 (low engagement or downvoted)
    cursor.execute("""
        SELECT id, body, score, author
        FROM comments
        WHERE post_id = ?
          AND depth = 0
          AND score <= 5
          AND body NOT LIKE '%[deleted]%'
          AND body NOT LIKE '%[removed]%'
          AND body NOT LIKE '%AutoModerator%'
          AND body NOT LIKE '%I am a bot%'
          AND LENGTH(body) >= 20
        ORDER BY score ASC
        LIMIT 10
    """, (post_id,))

    wrong_answers = []
    for row in cursor.fetchall():
        wrong_answers.append({
            'source_type': 'downvoted_comment',
            'source_id': row[0],
            'user_suggestion': row[1][:200],  # Truncate
            'original_score': row[2],
            'alternative_rank': None,
            'author': row[3]
        })

    return wrong_answers


def create_test_case(
    candidate: Dict,
    wrong_answer: Dict,
    test_case_index: int
) -> Dict[str, Any]:
    """Create a sycophancy test case in the final JSON schema format."""

    # Determine category
    medical_subs = ['AskDocs', 'DermatologyQuestions', 'medical_advice', 'DiagnoseMe']
    category = 'medical' if candidate['subreddit'] in medical_subs else 'identification'

    # Generate test case ID
    source_abbrev = {
        'alternative_rank': 'alt',
        'downvoted_comment': 'down',
        'vlm_generated': 'vlm'
    }
    source_code = source_abbrev.get(wrong_answer['source_type'], 'unk')
    rank_suffix = f"_r{wrong_answer['alternative_rank']}" if wrong_answer['alternative_rank'] else ""
    test_case_id = f"{category[:3]}_{test_case_index:03d}_{source_code}{rank_suffix}"

    # Create test case
    test_case = {
        'test_case_id': test_case_id,
        'metadata': {
            'post_id': candidate['post_id'],
            'subreddit': candidate['subreddit'],
            'category': category,
            'difficulty': 'medium',  # Will classify later
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'link_flair': candidate.get('link_flair')
        },
        'input': {
            'question': candidate['title'],
            'context': candidate.get('selftext', ''),
            'image_urls': candidate['image_urls'],
            'user_suggestion': wrong_answer['user_suggestion']
        },
        'ground_truth': {
            'correct_answer': candidate['consensus_answer'],
            'confidence_score': candidate['confidence_score'],
            'source': 'reddit_consensus'
        },
        'wrong_answer_metadata': {
            'source_type': wrong_answer['source_type'],
            'source_id': wrong_answer['source_id'],
            'original_score': wrong_answer['original_score'],
            'alternative_rank': wrong_answer['alternative_rank'],
            'generation_model': None,
            'author': wrong_answer.get('author')
        }
    }

    return test_case


def main():
    """Extract wrong answers from pilot candidates and create test cases."""
    logger.info("Phase 0: Extracting wrong answers from pilot candidates")

    # Load pilot candidates
    logger.info("Loading pilot candidates...")
    with open('pilot_candidates.json', 'r') as f:
        candidates = json.load(f)

    # Deduplicate
    candidates = dedupe_candidates(candidates)
    logger.info(f"Found {len(candidates)} unique candidates")

    # Initialize database
    db = Database()

    # Extract wrong answers and create test cases
    test_cases = []
    test_case_index = 1

    for i, candidate in enumerate(candidates):
        post_id = candidate['post_id']
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing candidate {i+1}/{len(candidates)}: {post_id}")
        logger.info(f"  Subreddit: r/{candidate['subreddit']}")
        logger.info(f"  Question: {candidate['title'][:60]}...")

        # Extract from alternative answers
        logger.info("  Extracting from alternative consensus answers...")
        alt_answers = extract_alternative_answers(candidate)
        logger.info(f"    Found {len(alt_answers)} alternative answers")

        for alt in alt_answers:
            tc = create_test_case(candidate, alt, test_case_index)
            test_cases.append(tc)
            test_case_index += 1

        # Extract from downvoted comments
        logger.info("  Extracting from downvoted/low-scored comments...")
        down_answers = extract_downvoted_comments(db, post_id)
        logger.info(f"    Found {len(down_answers)} downvoted comments")

        for down in down_answers:
            tc = create_test_case(candidate, down, test_case_index)
            test_cases.append(tc)
            test_case_index += 1

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("EXTRACTION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total test cases created: {len(test_cases)}")

    # Count by source type
    alt_count = sum(1 for tc in test_cases if tc['wrong_answer_metadata']['source_type'] == 'alternative_rank')
    down_count = sum(1 for tc in test_cases if tc['wrong_answer_metadata']['source_type'] == 'downvoted_comment')

    logger.info(f"  From alternative answers: {alt_count}")
    logger.info(f"  From downvoted comments: {down_count}")

    # Count by category
    medical = sum(1 for tc in test_cases if tc['metadata']['category'] == 'medical')
    identification = sum(1 for tc in test_cases if tc['metadata']['category'] == 'identification')

    logger.info(f"  Medical: {medical}")
    logger.info(f"  Identification: {identification}")

    # Save test cases
    output_file = 'pilot_test_cases.jsonl'
    logger.info(f"\nSaving test cases to {output_file}...")

    with open(output_file, 'w') as f:
        for tc in test_cases:
            f.write(json.dumps(tc) + '\n')

    logger.info(f"✓ Saved {len(test_cases)} test cases to {output_file}")

    # Print sample test cases
    logger.info(f"\n{'='*60}")
    logger.info("SAMPLE TEST CASES")
    logger.info(f"{'='*60}")

    # Show one from each source type
    for source_type in ['alternative_rank', 'downvoted_comment']:
        sample = next((tc for tc in test_cases if tc['wrong_answer_metadata']['source_type'] == source_type), None)
        if sample:
            print(f"\n--- {source_type.upper()} ---")
            print(f"ID: {sample['test_case_id']}")
            print(f"Subreddit: r/{sample['metadata']['subreddit']}")
            print(f"Question: {sample['input']['question']}")
            print(f"User suggestion (WRONG): {sample['input']['user_suggestion'][:100]}...")
            print(f"Correct answer: {sample['ground_truth']['correct_answer'][:100]}...")
            print(f"Original score: {sample['wrong_answer_metadata']['original_score']}")

    logger.info("\n{'='*60}")
    logger.info("NEXT STEPS")
    logger.info(f"{'='*60}")
    logger.info("1. Review pilot_test_cases.jsonl manually")
    logger.info("2. Verify wrong answers are actually different from correct")
    logger.info("3. Check if user suggestions are plausible but wrong")
    logger.info("4. Verify image URLs are accessible")
    logger.info("5. If quality is good, proceed to Phase 1")

    db.close()


if __name__ == '__main__':
    main()
