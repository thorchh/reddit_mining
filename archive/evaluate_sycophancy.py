#!/usr/bin/env python3
"""
Sycophancy Evaluation Framework

3-stage pipeline to test if VLMs can be tricked into agreeing with wrong answers:
1. Stage 1: Generate sycophantic prompts (GPT-4o-mini)
2. Stage 2: Test target VLM with prompts + images (GPT-4o Vision)
3. Stage 3: Verify if sycophancy occurred (GPT-4o)

Validates hypothesis: Higher sycophancy scores → Higher susceptibility
"""

import json
import argparse
import random
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import csv

from storage.database import Database
from generators.sycophancy_prompt_generator import SycophancyPromptGenerator
from generators.target_vlm_evaluator import TargetVLMEvaluator
from generators.sycophancy_eval_verifier import SycophancyEvalVerifier
from utils.logger import setup_logger

logger = setup_logger('evaluate_sycophancy')

# Medical subreddits
MEDICAL_SUBS = ['AskDocs', 'DermatologyQuestions', 'medical_advice', 'DiagnoseMe']


def load_checkpoint_data(checkpoint_file: Path) -> List[Dict[str, Any]]:
    """
    Load scored posts from checkpoint file.

    Args:
        checkpoint_file: Path to checkpoint JSON

    Returns:
        List of scored post results
    """
    with open(checkpoint_file, 'r') as f:
        data = json.load(f)
        return data.get('results', [])


def stratified_sample(scored_posts: List[Dict[str, Any]], sample_per_score: int) -> List[Dict[str, Any]]:
    """
    Stratified sampling by score level.

    Args:
        scored_posts: List of scored posts from checkpoint
        sample_per_score: Number to sample per score level

    Returns:
        Sampled posts
    """
    # Group by score
    by_score = {}
    for post in scored_posts:
        score = post.get('overall_score', 0)
        if score not in by_score:
            by_score[score] = []
        by_score[score].append(post)

    # Sample from each score level
    sampled = []
    for score in sorted(by_score.keys(), reverse=True):
        posts = by_score[score]
        n_sample = min(sample_per_score, len(posts))
        sampled.extend(random.sample(posts, n_sample))

    return sampled


def enrich_post_data(checkpoint_post: Dict[str, Any], database: Database) -> Dict[str, Any]:
    """
    Merge checkpoint scoring data with full post data from database.

    Args:
        checkpoint_post: Post from checkpoint (has scores, not full data)
        database: Database instance

    Returns:
        Enriched post data with all fields needed for evaluation
    """
    post_id = checkpoint_post['post_id']

    # Get full post data from database
    db_post = database.get_post_with_consensus(post_id)

    if not db_post:
        raise ValueError(f"Post {post_id} not found in database")

    # Determine category
    category = 'medical' if db_post['subreddit'] in MEDICAL_SUBS else 'identification'

    # Merge data
    return {
        'post_id': post_id,
        'original_score': checkpoint_post.get('overall_score', 0),
        'viable': checkpoint_post.get('viable', 'UNKNOWN'),
        'best_wrong_answer': checkpoint_post.get('best_wrong_answer', {}),

        # From database
        'title': db_post['title'],
        'selftext': db_post['selftext'],
        'image_urls': db_post['image_urls'],
        'subreddit': db_post['subreddit'],
        'consensus_answer': db_post['consensus_answer'],
        'confidence_score': db_post['confidence_score'],
        'category': category
    }


def evaluate_post(
    post_data: Dict[str, Any],
    prompt_generator: SycophancyPromptGenerator,
    target_evaluator: TargetVLMEvaluator,
    verifier: SycophancyEvalVerifier
) -> Dict[str, Any]:
    """
    Run 3-stage evaluation pipeline for a single post.

    Args:
        post_data: Enriched post data
        prompt_generator: Stage 1 generator
        target_evaluator: Stage 2 evaluator
        verifier: Stage 3 verifier

    Returns:
        Complete evaluation result
    """
    post_id = post_data['post_id']
    original_score = post_data['original_score']

    logger.info(f"  Post: {post_id} (score: {original_score})")

    # Stage 1: Generate sycophantic prompt
    logger.info("  Stage 1: Generating sycophantic prompt...")
    stage1_result = prompt_generator.generate_prompt(post_data)
    sycophantic_prompt = stage1_result.get('sycophantic_prompt', '')
    strategy = stage1_result.get('strategy', 'unknown')
    logger.info(f"    ✓ Generated ({strategy} strategy)")

    # Stage 2: Evaluate target VLM
    logger.info("  Stage 2: Evaluating target VLM...")
    stage2_result = target_evaluator.evaluate(
        sycophantic_prompt,
        post_data['image_urls']
    )
    vlm_response = stage2_result.get('vlm_response', '')
    logger.info(f"    ✓ VLM responded ({len(vlm_response)} chars)")

    # Stage 3: Verify sycophancy
    logger.info("  Stage 3: Verifying sycophancy...")
    wrong_answer_text = post_data['best_wrong_answer'].get('comment_text', '')
    stage3_result = verifier.verify(
        ground_truth=post_data['consensus_answer'] or '',
        wrong_answer=wrong_answer_text,
        vlm_response=vlm_response,
        sycophantic_prompt=sycophantic_prompt,
        subreddit=post_data['subreddit'],
        title=post_data['title']
    )
    verdict = stage3_result.get('sycophancy_verdict', 'UNKNOWN')
    confidence = stage3_result.get('confidence', 0.0)
    logger.info(f"    ✓ Verdict: {verdict} (confidence: {confidence:.2f})")

    # Calculate total cost
    total_cost = (
        stage1_result.get('cost_usd', 0) +
        stage2_result.get('cost_usd', 0) +
        stage3_result.get('cost_usd', 0)
    )

    # Build result
    result = {
        'post_id': post_id,
        'original_score': original_score,
        'subreddit': post_data['subreddit'],
        'category': post_data['category'],
        'title': post_data['title'],
        'num_images': len(post_data['image_urls']),
        'ground_truth': post_data['consensus_answer'],
        'wrong_answer_suggested': wrong_answer_text,

        'stage1_prompt': stage1_result,
        'stage2_vlm_response': stage2_result,
        'stage3_verification': stage3_result,

        'sycophancy_detected': verdict in ['YES', 'PARTIAL'],
        'total_cost_usd': total_cost
    }

    logger.info(f"  Completed. Cost: ${total_cost:.4f}")
    logger.info("")

    return result


def save_checkpoint(results: List[Dict[str, Any]], checkpoint_file: Path, metadata: Dict[str, Any]):
    """Save evaluation checkpoint."""
    with open(checkpoint_file, 'w') as f:
        json.dump({
            'metadata': metadata,
            'results': results
        }, f, indent=2)


def generate_summary_csv(results: List[Dict[str, Any]], output_file: Path):
    """Generate CSV summary of results."""
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'post_id', 'original_score', 'subreddit', 'category',
            'sycophancy_verdict', 'confidence', 'strategy',
            'explicit_agreement', 'correction_attempted', 'total_cost'
        ])

        for r in results:
            stage1 = r.get('stage1_prompt', {})
            stage3 = r.get('stage3_verification', {})
            classification = stage3.get('classification', {})

            writer.writerow([
                r['post_id'],
                r['original_score'],
                r['subreddit'],
                r['category'],
                stage3.get('sycophancy_verdict', 'UNKNOWN'),
                stage3.get('confidence', 0.0),
                stage1.get('strategy', 'unknown'),
                classification.get('explicit_agreement', False),
                classification.get('correction_attempted', False),
                r['total_cost_usd']
            ])


def generate_statistics_by_score(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate aggregated statistics by score level."""
    stats_by_score = {}

    # Group by score
    by_score = {}
    for r in results:
        score = r['original_score']
        if score not in by_score:
            by_score[score] = []
        by_score[score].append(r)

    # Calculate stats for each score level
    for score, posts in by_score.items():
        yes_count = sum(1 for p in posts if p.get('stage3_verification', {}).get('sycophancy_verdict') == 'YES')
        partial_count = sum(1 for p in posts if p.get('stage3_verification', {}).get('sycophancy_verdict') == 'PARTIAL')
        total = len(posts)

        confidences = [p.get('stage3_verification', {}).get('confidence', 0.0) for p in posts]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Strategy distribution
        strategies = {}
        for p in posts:
            strat = p.get('stage1_prompt', {}).get('strategy', 'unknown')
            strategies[strat] = strategies.get(strat, 0) + 1

        stats_by_score[f"score_{score}"] = {
            'total_posts': total,
            'sycophancy_yes': yes_count,
            'sycophancy_partial': partial_count,
            'sycophancy_no': total - yes_count - partial_count,
            'sycophancy_rate': (yes_count + partial_count) / total if total > 0 else 0.0,
            'avg_confidence': avg_confidence,
            'strategy_distribution': strategies
        }

    # Calculate correlation
    try:
        from scipy.stats import spearmanr

        scores = [r['original_score'] for r in results]
        syc_detected = [1 if r['sycophancy_detected'] else 0 for r in results]

        correlation, p_value = spearmanr(scores, syc_detected)

        stats_by_score['correlation_analysis'] = {
            'spearman_correlation': correlation,
            'p_value': p_value,
            'interpretation': 'Strong positive correlation' if correlation > 0.6 and p_value < 0.01 else 'Moderate or weak correlation'
        }
    except ImportError:
        logger.warning("scipy not installed, skipping correlation analysis")

    return stats_by_score


def main():
    parser = argparse.ArgumentParser(
        description='Evaluate VLM sycophancy susceptibility across score levels'
    )
    parser.add_argument(
        '--checkpoint',
        type=Path,
        required=True,
        help='Path to scoring checkpoint JSON file'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('output/sycophancy_evaluation'),
        help='Output directory for results'
    )
    parser.add_argument(
        '--sample-per-score',
        type=int,
        default=20,
        help='Number of posts to sample per score level (default: 20)'
    )
    parser.add_argument(
        '--scores',
        type=str,
        default='2,3,4,5,6,7,8,9',
        help='Comma-separated score levels to evaluate (default: 2-9)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show cost estimate without running evaluation'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )
    parser.add_argument(
        '--api-key',
        help='OpenAI API key (or set OPENAI_API_KEY env var)'
    )

    args = parser.parse_args()

    # Parse score levels
    score_levels = [int(s.strip()) for s in args.scores.split(',')]

    logger.info("="*80)
    logger.info("SYCOPHANCY EVALUATION FRAMEWORK")
    logger.info("="*80)
    logger.info(f"Checkpoint: {args.checkpoint}")
    logger.info(f"Score levels: {score_levels}")
    logger.info(f"Sample per score: {args.sample_per_score}")
    logger.info("")

    # Load checkpoint data
    logger.info("Loading checkpoint data...")
    scored_posts = load_checkpoint_data(args.checkpoint)
    logger.info(f"✓ Loaded {len(scored_posts)} scored posts")

    # Filter by requested scores
    filtered_posts = [p for p in scored_posts if p.get('overall_score', 0) in score_levels]
    logger.info(f"✓ Filtered to {len(filtered_posts)} posts matching score levels")

    # Stratified sampling
    logger.info(f"Sampling {args.sample_per_score} posts per score level...")
    sampled_posts = stratified_sample(filtered_posts, args.sample_per_score)
    logger.info(f"✓ Sampled {len(sampled_posts)} posts total")
    logger.info("")

    # Show sampling breakdown
    sample_counts = {}
    for p in sampled_posts:
        score = p.get('overall_score', 0)
        sample_counts[score] = sample_counts.get(score, 0) + 1

    logger.info("Sampling breakdown:")
    for score in sorted(sample_counts.keys(), reverse=True):
        logger.info(f"  Score {score}: {sample_counts[score]} posts")
    logger.info("")

    # Initialize components
    logger.info("Initializing evaluation components...")
    prompt_generator = SycophancyPromptGenerator(api_key=args.api_key)
    target_evaluator = TargetVLMEvaluator(api_key=args.api_key)
    verifier = SycophancyEvalVerifier(api_key=args.api_key)
    logger.info("✓ Components initialized")
    logger.info("")

    # Cost estimates
    stage1_est = prompt_generator.get_cost_estimate(len(sampled_posts))
    stage2_est = target_evaluator.get_cost_estimate(len(sampled_posts))
    stage3_est = verifier.get_cost_estimate(len(sampled_posts))

    total_min = stage1_est['estimated_total_cost'] + stage2_est['cost_range']['min'] + stage3_est['estimated_total_cost']
    total_max = stage1_est['estimated_total_cost'] + stage2_est['cost_range']['max'] + stage3_est['estimated_total_cost']

    logger.info("Cost Estimates:")
    logger.info(f"  Stage 1 (Prompt Gen):  ${stage1_est['estimated_total_cost']:.2f}")
    logger.info(f"  Stage 2 (VLM Eval):    ${stage2_est['cost_range']['min']:.2f} - ${stage2_est['cost_range']['max']:.2f}")
    logger.info(f"  Stage 3 (Verifier):    ${stage3_est['estimated_total_cost']:.2f}")
    logger.info(f"  Total estimated cost:  ${total_min:.2f} - ${total_max:.2f}")
    logger.info("")

    if args.dry_run:
        logger.info("DRY RUN - Exiting without evaluation")
        return

    # Confirm
    if not args.yes:
        response = input(f"Proceed with evaluating {len(sampled_posts)} posts? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            logger.info("Cancelled by user")
            return

    logger.info("")
    logger.info("="*80)
    logger.info("EVALUATION")
    logger.info("="*80)
    logger.info("")

    # Initialize database
    db = Database()

    # Prepare output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = args.output_dir / 'checkpoint_evaluation.json'

    # Load existing checkpoint if it exists
    results = []
    processed_ids = set()
    if checkpoint_file.exists():
        logger.info(f"Loading existing checkpoint from {checkpoint_file}...")
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
            results = checkpoint_data.get('results', [])
            processed_ids = {r['post_id'] for r in results}
        logger.info(f"  Resuming from {len(results)} already evaluated posts")
        logger.info("")

    # Filter out already processed
    to_process = [p for p in sampled_posts if p['post_id'] not in processed_ids]

    logger.info(f"Evaluating {len(to_process)} posts (Total: {len(sampled_posts)}, Already done: {len(processed_ids)})...")
    logger.info("")

    # Process posts
    for i, checkpoint_post in enumerate(to_process, 1):
        total_idx = len(processed_ids) + i
        logger.info(f"[{total_idx}/{len(sampled_posts)}] Evaluating...")

        # Enrich with database data
        try:
            post_data = enrich_post_data(checkpoint_post, db)
        except ValueError as e:
            logger.error(f"  ERROR: {e}")
            continue

        # Run 3-stage pipeline
        result = evaluate_post(post_data, prompt_generator, target_evaluator, verifier)
        results.append(result)

        # Save checkpoint every 10 posts
        if i % 10 == 0:
            metadata = {
                'total_evaluated': len(results),
                'total_cost_usd': sum(r['total_cost_usd'] for r in results),
                'last_updated': datetime.utcnow().isoformat() + 'Z'
            }
            save_checkpoint(results, checkpoint_file, metadata)
            logger.info(f"  💾 Checkpoint saved ({len(results)} posts)")
            logger.info("")

    # Final save
    metadata = {
        'total_evaluated': len(results),
        'total_cost_usd': sum(r['total_cost_usd'] for r in results),
        'completed_at': datetime.utcnow().isoformat() + 'Z',
        'models': {
            'prompt_generator': 'gpt-4o-mini',
            'target_vlm': 'gpt-4o',
            'verifier': 'gpt-4o'
        }
    }
    save_checkpoint(results, checkpoint_file, metadata)

    logger.info("")
    logger.info("="*80)
    logger.info("RESULTS")
    logger.info("="*80)
    logger.info("")

    # Generate outputs
    full_results_file = args.output_dir / 'results_full.json'
    with open(full_results_file, 'w') as f:
        json.dump({'metadata': metadata, 'results': results}, f, indent=2)
    logger.info(f"✓ Saved full results to {full_results_file}")

    summary_csv_file = args.output_dir / 'results_summary.csv'
    generate_summary_csv(results, summary_csv_file)
    logger.info(f"✓ Saved summary CSV to {summary_csv_file}")

    stats_by_score = generate_statistics_by_score(results)
    stats_file = args.output_dir / 'results_by_score.json'
    with open(stats_file, 'w') as f:
        json.dump(stats_by_score, f, indent=2)
    logger.info(f"✓ Saved statistics by score to {stats_file}")

    logger.info("")
    logger.info("Summary:")
    logger.info(f"  Total posts evaluated: {len(results)}")
    logger.info(f"  Total cost: ${metadata['total_cost_usd']:.2f}")
    logger.info(f"  Sycophancy detected: {sum(1 for r in results if r['sycophancy_detected'])}/{len(results)}")
    logger.info("")

    # Show correlation if available
    if 'correlation_analysis' in stats_by_score:
        corr = stats_by_score['correlation_analysis']
        logger.info(f"Correlation: {corr['spearman_correlation']:.3f} (p={corr['p_value']:.4f})")
        logger.info(f"Interpretation: {corr['interpretation']}")

    logger.info("")
    logger.info("="*80)
    logger.info("COMPLETE")
    logger.info("="*80)

    db.close()


if __name__ == '__main__':
    main()
