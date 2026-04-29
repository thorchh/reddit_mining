#!/usr/bin/env python3
"""
Test the LLM verifier on a single post to see output quality.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.database import Database
from generators.llm_verifier import SycophancyVerifier


def main():
    print("Testing LLM Verifier on single post...")
    print()

    # Get one candidate post
    db = Database()
    candidates = db.get_sycophancy_candidates(limit=1)

    if not candidates:
        print("No candidates found!")
        return

    post = candidates[0]

    print("="*80)
    print("TEST POST")
    print("="*80)
    print(f"Post ID: {post['post_id']}")
    print(f"Subreddit: r/{post['subreddit']}")
    print(f"Question: {post['title']}")
    print(f"Confidence: {post['confidence_score']:.3f}")
    print(f"Images: {len(post['image_urls'])}")
    print(f"Top score: {post['top_comment_score']}")
    print(f"Second score: {post['second_comment_score']}")
    print(f"Ratio: {post['top_comment_score'] / post['second_comment_score']:.2f}x")
    print()

    print("Top answers:")
    for i, ans in enumerate(post['top_answers'][:3], 1):
        print(f"  [{i}] (Score: {ans['score']}) {ans['answer'][:80]}...")
    print()

    # Initialize verifier
    print("Initializing LLM verifier...")
    verifier = SycophancyVerifier()

    # Show cost estimate
    estimate = verifier.get_cost_estimate(1)
    print(f"Estimated cost for 1 post: ${estimate['estimated_total_cost']:.4f}")
    print()

    # Confirm
    response = input("Proceed with verification? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cancelled")
        db.close()
        return

    print()
    print("="*80)
    print("VERIFYING POST")
    print("="*80)
    print()

    # Verify
    result = verifier.verify_post(post)

    print()
    print("="*80)
    print("VERIFICATION RESULT")
    print("="*80)
    print()

    print(f"Sycophancy Score: {result['sycophancy_score']}/10")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Cost: ${result['_metadata']['cost_usd']:.4f}")
    print()

    print("Analysis:")
    print("-" * 80)
    analysis = result.get('analysis', {})
    for key, value in analysis.items():
        if key != 'error':
            print(f"\n{key.replace('_', ' ').title()}:")
            print(f"  {value}")
    print()

    if result.get('test_case'):
        print("="*80)
        print("GENERATED TEST CASE")
        print("="*80)
        print()
        print(json.dumps(result['test_case'], indent=2))
        print()

        # Save for inspection
        with open('test_verifier_output.json', 'w') as f:
            json.dump(result, f, indent=2)
        print("✓ Saved full output to test_verifier_output.json")

    db.close()


if __name__ == '__main__':
    main()
