#!/usr/bin/env python3
"""
Build sycophancy dataset using LLM verification.

Uses GPT-4o-mini to:
1. Analyze all candidate posts
2. Score sycophancy potential
3. Select best wrong answers
4. Generate complete test cases
5. Rank and filter to top 200
"""

import json
import argparse
from pathlib import Path
from typing import Optional

from storage.database import Database
from generators.llm_verifier import SycophancyVerifier
from utils.logger import setup_logger

logger = setup_logger('build_sycophancy_dataset')


def main():
    parser = argparse.ArgumentParser(
        description='Build sycophancy dataset with LLM verification'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=250,
        help='Number of candidate posts to fetch (default: 250)'
    )
    parser.add_argument(
        '--category',
        choices=['medical', 'identification', 'all'],
        default='all',
        help='Category to process (default: all)'
    )
    parser.add_argument(
        '--min-score',
        type=int,
        default=6,
        help='Minimum sycophancy score to include (1-10, default: 6)'
    )
    parser.add_argument(
        '--max-results',
        type=int,
        default=200,
        help='Maximum test cases to generate (default: 200)'
    )
    parser.add_argument(
        '--api-key',
        help='OpenAI API key (or set OPENAI_API_KEY env var)'
    )
    parser.add_argument(
        '--model',
        default='gpt-4o-mini',
        help='OpenAI model to use (default: gpt-4o-mini)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show cost estimate without running'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('output/sycophancy_datasets'),
        help='Output directory (default: output/sycophancy_datasets)'
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("SYCOPHANCY DATASET BUILDER")
    logger.info("="*80)
    logger.info(f"Model: {args.model}")
    logger.info(f"Category: {args.category}")
    logger.info(f"Candidate limit: {args.limit}")
    logger.info(f"Min sycophancy score: {args.min_score}")
    logger.info(f"Max results: {args.max_results}")
    logger.info("")

    # Initialize database
    logger.info("Connecting to database...")
    db = Database()

    # Fetch candidates
    logger.info(f"Fetching up to {args.limit} candidate posts...")
    category_filter = None if args.category == 'all' else args.category
    candidates = db.get_sycophancy_candidates(
        limit=args.limit,
        category=category_filter
    )
    logger.info(f"✓ Found {len(candidates)} candidates")
    logger.info("")

    # Initialize verifier
    logger.info("Initializing LLM verifier...")
    verifier = SycophancyVerifier(
        api_key=args.api_key,
        model=args.model
    )

    # Cost estimate
    estimate = verifier.get_cost_estimate(len(candidates))
    logger.info("Cost Estimate:")
    logger.info(f"  Posts to verify: {estimate['num_posts']}")
    logger.info(f"  Estimated tokens: {estimate['estimated_input_tokens']:,} input, {estimate['estimated_output_tokens']:,} output")
    logger.info(f"  Estimated cost: ${estimate['estimated_total_cost']:.2f}")
    logger.info("")

    if args.dry_run:
        logger.info("DRY RUN - Exiting without processing")
        db.close()
        return

    # Confirm before proceeding
    response = input(f"Proceed with LLM verification? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        logger.info("Cancelled by user")
        db.close()
        return

    logger.info("")
    logger.info("="*80)
    logger.info("VERIFYING POSTS WITH LLM")
    logger.info("="*80)
    logger.info("")

    # Verify all candidates
    results = verifier.verify_batch(
        posts=candidates,
        min_score=args.min_score,
        max_results=args.max_results
    )

    logger.info("="*80)
    logger.info("VERIFICATION RESULTS")
    logger.info("="*80)
    logger.info(f"Accepted: {len(results)} test cases")
    logger.info(f"Total cost: ${verifier.total_cost:.4f}")
    logger.info("")

    if len(results) == 0:
        logger.warning("No test cases passed verification!")
        logger.warning("Consider lowering --min-score or relaxing selection criteria")
        db.close()
        return

    # Statistics
    scores = [r['sycophancy_score'] for r in results]
    logger.info("Score distribution:")
    logger.info(f"  Min: {min(scores)}")
    logger.info(f"  Max: {max(scores)}")
    logger.info(f"  Avg: {sum(scores)/len(scores):.2f}")
    logger.info("")

    # Category breakdown
    categories = {}
    difficulties = {}
    for r in results:
        tc = r['test_case']
        cat = tc['metadata']['category']
        diff = tc['metadata']['difficulty']
        categories[cat] = categories.get(cat, 0) + 1
        difficulties[diff] = difficulties.get(diff, 0) + 1

    logger.info("Category breakdown:")
    for cat, count in sorted(categories.items()):
        logger.info(f"  {cat}: {count}")
    logger.info("")

    logger.info("Difficulty breakdown:")
    for diff, count in sorted(difficulties.items()):
        logger.info(f"  {diff}: {count}")
    logger.info("")

    # Save results
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Save test cases by category
    logger.info("="*80)
    logger.info("SAVING DATASETS")
    logger.info("="*80)

    if args.category == 'all':
        # Save separate files for each category
        for category in categories.keys():
            category_results = [r for r in results if r['test_case']['metadata']['category'] == category]
            output_file = args.output_dir / f"sycophancy_dataset_{category}.jsonl"

            with open(output_file, 'w') as f:
                for r in category_results:
                    f.write(json.dumps(r['test_case']) + '\n')

            logger.info(f"✓ Saved {len(category_results)} {category} cases to {output_file}")
    else:
        # Save single category file
        output_file = args.output_dir / f"sycophancy_dataset_{args.category}.jsonl"
        with open(output_file, 'w') as f:
            for r in results:
                f.write(json.dumps(r['test_case']) + '\n')
        logger.info(f"✓ Saved {len(results)} cases to {output_file}")

    # Save full results with analysis
    full_output_file = args.output_dir / "verification_results_full.json"
    with open(full_output_file, 'w') as f:
        json.dump({
            'metadata': {
                'total_candidates': len(candidates),
                'accepted_cases': len(results),
                'model': args.model,
                'min_score': args.min_score,
                'total_cost_usd': verifier.total_cost,
                'timestamp': results[0]['_metadata']['timestamp'] if results else None
            },
            'results': results
        }, f, indent=2)
    logger.info(f"✓ Saved full results with analysis to {full_output_file}")

    # Save statistics
    stats_file = args.output_dir / "dataset_statistics.json"
    with open(stats_file, 'w') as f:
        json.dump({
            'total_test_cases': len(results),
            'categories': categories,
            'difficulties': difficulties,
            'score_distribution': {
                'min': min(scores),
                'max': max(scores),
                'avg': sum(scores) / len(scores),
                'scores': scores
            },
            'cost': {
                'total_usd': verifier.total_cost,
                'per_case_usd': verifier.total_cost / len(results) if results else 0
            }
        }, f, indent=2)
    logger.info(f"✓ Saved statistics to {stats_file}")

    logger.info("")
    logger.info("="*80)
    logger.info("COMPLETE")
    logger.info("="*80)
    logger.info(f"Generated {len(results)} sycophancy test cases")
    logger.info(f"Total cost: ${verifier.total_cost:.4f}")
    logger.info(f"Output directory: {args.output_dir}")

    db.close()


if __name__ == '__main__':
    main()
