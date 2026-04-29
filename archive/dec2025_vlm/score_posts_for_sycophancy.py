#!/usr/bin/env python3
"""
Score posts for sycophancy potential at scale.

Analyzes 1000-2000 posts using consistent LLM scoring to identify
the most sycophantic candidates.

Process:
1. Fetch posts (heuristically sorted by score ratio)
2. Score each with LLM using consistent rubric
3. Rank by sycophancy potential
4. Save top N for test case generation
"""

import json
import argparse
from pathlib import Path

from storage.database import Database
from generators.sycophancy_scorer import SycophancyScorer
from utils.logger import setup_logger

logger = setup_logger('score_posts_for_sycophancy')


def main():
    parser = argparse.ArgumentParser(
        description='Score posts for sycophancy potential'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=1800,
        help='Number of posts to score (default: 1800)'
    )
    parser.add_argument(
        '--category',
        choices=['medical', 'identification', 'all'],
        default='all',
        help='Category to process (default: all)'
    )
    parser.add_argument(
        '--min-viable-score',
        type=int,
        default=6,
        help='Minimum score to mark as viable (1-10, default: 6)'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=300,
        help='Save top N highest scoring posts (default: 300)'
    )
    parser.add_argument(
        '--api-key',
        help='OpenAI API key (or set OPENAI_API_KEY env var)'
    )
    parser.add_argument(
        '--model',
        default='gpt-4o',
        help='OpenAI model to use (default: gpt-4o with vision)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show cost estimate without running'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('output/scoring_results'),
        help='Output directory (default: output/scoring_results)'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("SYCOPHANCY POST SCORER")
    logger.info("="*80)
    logger.info(f"Model: {args.model}")
    logger.info(f"Category: {args.category}")
    logger.info(f"Posts to score: {args.limit}")
    logger.info(f"Min viable score: {args.min_viable_score}")
    logger.info(f"Will save top {args.top_n} posts")
    logger.info("")

    # Initialize database
    logger.info("Connecting to database...")
    db = Database()

    # Fetch posts with top 10 comments
    logger.info(f"Fetching up to {args.limit} posts (with top 10 comments each)...")
    logger.info("Using heuristic sorting: score ratio ASC, confidence ASC")
    category_filter = None if args.category == 'all' else args.category
    posts = db.get_posts_for_scoring(
        limit=args.limit,
        category=category_filter
    )
    logger.info(f"✓ Found {len(posts)} posts")

    if len(posts) == 0:
        logger.error("No posts found matching criteria!")
        db.close()
        return

    # Show sample
    sample = posts[0]
    logger.info("")
    logger.info("Sample post:")
    logger.info(f"  ID: {sample['post_id']}")
    logger.info(f"  Subreddit: r/{sample['subreddit']}")
    logger.info(f"  Question: {sample['title'][:60]}...")
    logger.info(f"  Images: {len(sample['image_urls'])}")
    logger.info(f"  Top 10 comments: {len(sample['top_10_comments'])}")
    logger.info(f"  Confidence: {sample['confidence_score']:.3f}")
    logger.info("")

    # Initialize scorer
    logger.info("Initializing LLM scorer...")
    scorer = SycophancyScorer(
        api_key=args.api_key,
        model=args.model
    )

    # Cost estimate
    estimate = scorer.get_cost_estimate(len(posts))
    logger.info("Cost Estimate:")
    logger.info(f"  Posts to score: {estimate['num_posts']}")
    logger.info(f"  Estimated tokens: {estimate['estimated_input_tokens']:,} input, {estimate['estimated_output_tokens']:,} output")
    logger.info(f"  Estimated cost: ${estimate['estimated_total_cost']:.2f}")
    logger.info("")

    if args.dry_run:
        logger.info("DRY RUN - Exiting without processing")
        db.close()
        return

    # Confirm before proceeding
    if not args.yes:
        response = input(f"Proceed with scoring {len(posts)} posts? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            logger.info("Cancelled by user")
            db.close()
            return
    else:
        logger.info("Auto-confirmed with --yes flag")

    logger.info("")
    logger.info("="*80)
    logger.info("SCORING POSTS")
    logger.info("="*80)
    logger.info("")

    # Set up checkpoint file
    checkpoint_file = args.output_dir / f"checkpoint_{len(posts)}posts.json"

    # Score all posts with checkpointing
    results = scorer.score_batch(
        posts=posts,
        min_viable_score=args.min_viable_score,
        checkpoint_file=checkpoint_file,
        save_every=10  # Save every 10 posts
    )

    logger.info("="*80)
    logger.info("SCORING RESULTS")
    logger.info("="*80)
    logger.info(f"Scored: {len(results)} posts")
    logger.info(f"Total cost: ${scorer.total_cost:.2f}")
    logger.info("")

    # Statistics
    scores = [r.get('overall_score', 0) for r in results]
    viable_count = sum(1 for r in results if r.get('viable') == 'YES')

    logger.info("Score distribution:")
    logger.info(f"  Min: {min(scores)}")
    logger.info(f"  Max: {max(scores)}")
    logger.info(f"  Avg: {sum(scores)/len(scores):.2f}")
    logger.info(f"  Median: {sorted(scores)[len(scores)//2]}")
    logger.info("")

    # Score buckets
    buckets = {
        '9-10 (excellent)': sum(1 for s in scores if s >= 9),
        '7-8 (good)': sum(1 for s in scores if 7 <= s < 9),
        '5-6 (fair)': sum(1 for s in scores if 5 <= s < 7),
        '3-4 (poor)': sum(1 for s in scores if 3 <= s < 5),
        '1-2 (very poor)': sum(1 for s in scores if s < 3)
    }

    logger.info("Score buckets:")
    for bucket, count in buckets.items():
        pct = count / len(scores) * 100
        logger.info(f"  {bucket}: {count} ({pct:.1f}%)")
    logger.info("")

    logger.info(f"Viable posts: {viable_count}/{len(results)} ({viable_count/len(results)*100:.1f}%)")
    logger.info("")

    # Category breakdown
    categories = {}
    for r in results:
        # Determine category from post data
        post = next((p for p in posts if p['post_id'] == r.get('post_id')), None)
        if post:
            cat = 'medical' if post['subreddit'] in ['AskDocs', 'DermatologyQuestions', 'medical_advice', 'DiagnoseMe'] else 'identification'
            categories[cat] = categories.get(cat, 0) + 1

    logger.info("Category breakdown:")
    for cat, count in sorted(categories.items()):
        logger.info(f"  {cat}: {count}")
    logger.info("")

    # Save results
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Save full results
    full_output_file = args.output_dir / f"scoring_results_full_{len(results)}posts.json"
    with open(full_output_file, 'w') as f:
        json.dump({
            'metadata': {
                'total_posts_scored': len(results),
                'viable_posts': viable_count,
                'model': args.model,
                'min_viable_score': args.min_viable_score,
                'total_cost_usd': scorer.total_cost,
                'timestamp': results[0]['_metadata'].get('timestamp') if results and '_metadata' in results[0] else None
            },
            'score_distribution': {
                'min': min(scores),
                'max': max(scores),
                'avg': sum(scores) / len(scores),
                'median': sorted(scores)[len(scores)//2],
                'buckets': buckets
            },
            'results': results
        }, f, indent=2)
    logger.info(f"✓ Saved full results to {full_output_file}")

    # Save top N for test case generation
    top_n_results = results[:args.top_n]
    top_n_file = args.output_dir / f"top_{args.top_n}_posts.json"

    with open(top_n_file, 'w') as f:
        json.dump({
            'metadata': {
                'selected_count': len(top_n_results),
                'total_scored': len(results),
                'min_score_in_selection': min(r.get('overall_score', 0) for r in top_n_results),
                'max_score_in_selection': max(r.get('overall_score', 0) for r in top_n_results),
                'avg_score_in_selection': sum(r.get('overall_score', 0) for r in top_n_results) / len(top_n_results)
            },
            'posts': top_n_results
        }, f, indent=2)
    logger.info(f"✓ Saved top {len(top_n_results)} posts to {top_n_file}")

    # Save CSV summary for easy review
    csv_file = args.output_dir / f"scoring_summary_{len(results)}posts.csv"
    with open(csv_file, 'w') as f:
        f.write("post_id,subreddit,overall_score,viable,visual_ambiguity,answer_competition,wrong_answer_plausibility,semantic_disagreement,stakes\n")
        for r in results:
            post_id = r.get('post_id', 'unknown')
            post = next((p for p in posts if p['post_id'] == post_id), None)
            subreddit = post['subreddit'] if post else 'unknown'
            overall = r.get('overall_score', 0)
            viable = r.get('viable_for_sycophancy', 'UNKNOWN')

            dim_scores = r.get('dimension_scores', {})
            visual = dim_scores.get('visual_ambiguity', {}).get('score', 0)
            competition = dim_scores.get('answer_competition', {}).get('score', 0)
            plausibility = dim_scores.get('wrong_answer_plausibility', {}).get('score', 0)
            disagreement = dim_scores.get('semantic_disagreement', {}).get('score', 0)
            stakes = dim_scores.get('stakes', {}).get('score', 0)

            f.write(f"{post_id},{subreddit},{overall},{viable},{visual},{competition},{plausibility},{disagreement},{stakes}\n")
    logger.info(f"✓ Saved CSV summary to {csv_file}")

    logger.info("")
    logger.info("="*80)
    logger.info("COMPLETE")
    logger.info("="*80)
    logger.info(f"Scored {len(results)} posts")
    logger.info(f"Total cost: ${scorer.total_cost:.2f}")
    logger.info(f"Top {len(top_n_results)} posts saved for test case generation")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info("")
    logger.info("Next steps:")
    logger.info(f"  1. Review top_{args.top_n}_posts.json")
    logger.info("  2. Check scoring_summary CSV for patterns")
    logger.info("  3. Generate test cases from top posts")

    db.close()


if __name__ == '__main__':
    main()
