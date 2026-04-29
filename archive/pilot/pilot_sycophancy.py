#!/usr/bin/env python3
"""
Phase 0: Pilot script for sycophancy dataset validation

Find 10 candidate posts and inspect their quality for sycophancy testing.
"""

import json
from storage.database import Database
from utils.logger import setup_logger

logger = setup_logger('pilot_sycophancy')


def inspect_candidate(candidate: dict, index: int):
    """Pretty print a candidate post for manual inspection."""
    print(f"\n{'='*80}")
    print(f"CANDIDATE #{index + 1}")
    print(f"{'='*80}")
    print(f"Post ID: {candidate['post_id']}")
    print(f"Subreddit: r/{candidate['subreddit']}")
    print(f"Flair: {candidate['link_flair']}")
    print(f"\nQUESTION:")
    print(f"  {candidate['title']}")
    if candidate['selftext']:
        print(f"\nCONTEXT:")
        print(f"  {candidate['selftext'][:200]}...")

    print(f"\nIMAGES:")
    for img_url in candidate['image_urls']:
        print(f"  {img_url}")

    print(f"\nCONSENSUS (Correct Answer):")
    print(f"  {candidate['consensus_answer'][:200]}...")
    print(f"  Confidence: {candidate['confidence_score']:.3f}")
    print(f"  Top score: {candidate['top_comment_score']}")
    print(f"  2nd score: {candidate['second_comment_score']}")
    print(f"  Ratio: {candidate['top_comment_score'] / candidate['second_comment_score']:.2f}x")

    print(f"\nALTERNATIVE ANSWERS (Potential Wrong Answers):")
    for i, alt in enumerate(candidate['top_answers'][1:4], 2):  # Skip rank 1
        print(f"  Rank {alt['rank']} (score={alt['score']}): {alt['answer'][:100]}...")

    print(f"\nQUALITY INDICATORS:")
    print(f"  ✓ Has images: {len(candidate['image_urls'])} image(s)")
    print(f"  ✓ Has alternatives: {len(candidate['top_answers']) - 1} alternatives")
    print(f"  ✓ Medium confidence: {0.5 <= candidate['confidence_score'] < 0.95}")
    print(f"  ✓ Close competition: {candidate['top_comment_score'] / candidate['second_comment_score'] < 2.5}")
    print(f"  ✓ Good engagement: {candidate['total_comments']} comments")


def main():
    """Find and inspect 10 pilot candidates."""
    logger.info("Phase 0: Finding sycophancy pilot candidates")

    # Initialize database
    db = Database()

    # Get 10 candidates
    logger.info("Querying for 10 best sycophancy candidates...")
    candidates = db.get_sycophancy_candidates(limit=10)

    if len(candidates) < 10:
        logger.warning(f"Only found {len(candidates)} candidates (expected 10)")
        logger.warning("Consider relaxing selection criteria")
    else:
        logger.info(f"✓ Found {len(candidates)} candidates")

    # Inspect each candidate
    for i, candidate in enumerate(candidates):
        inspect_candidate(candidate, i)

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total candidates found: {len(candidates)}")

    if candidates:
        avg_confidence = sum(c['confidence_score'] for c in candidates) / len(candidates)
        avg_ratio = sum(c['top_comment_score'] / c['second_comment_score'] for c in candidates) / len(candidates)

        print(f"Average confidence: {avg_confidence:.3f}")
        print(f"Average score ratio: {avg_ratio:.2f}x")

        # Category breakdown
        medical = sum(1 for c in candidates if c['subreddit'] in ['AskDocs', 'DermatologyQuestions', 'medical_advice', 'DiagnoseMe'])
        identification = len(candidates) - medical
        print(f"Medical: {medical}, Identification: {identification}")

    # Save to JSON for inspection
    output_file = 'pilot_candidates.json'
    with open(output_file, 'w') as f:
        json.dump(candidates, f, indent=2)
    logger.info(f"Saved candidates to {output_file}")

    print(f"\n{'='*80}")
    print("NEXT STEPS")
    print(f"{'='*80}")
    print("1. Review the candidates above")
    print("2. Check if images load correctly")
    print("3. Verify alternatives are plausible but wrong")
    print("4. If 8/10 are usable, proceed to Phase 1")
    print("5. If not, adjust selection criteria in database.py")

    db.close()


if __name__ == '__main__':
    main()
