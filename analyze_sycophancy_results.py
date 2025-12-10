#!/usr/bin/env python3
"""
Post-hoc Analysis: Verify correctness of VLM responses

Analyzes completed sycophancy evaluation results to determine:
1. How often the VLM was actually correct (matched Reddit consensus)
2. Patterns in when sycophancy led to wrong answers
3. Comparison with control group (optional)

Uses ConsensusVerifier to check VLM responses against ground truth.
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any
import csv

from storage.database import Database
from generators.consensus_verifier import ConsensusVerifier
from utils.logger import setup_logger

logger = setup_logger('analyze_results')


def load_evaluation_results(results_file: Path) -> List[Dict[str, Any]]:
    """Load evaluation results from JSON file."""
    with open(results_file, 'r') as f:
        data = json.load(f)
        return data.get('results', [])


def enrich_with_database(result: Dict[str, Any], database: Database) -> Dict[str, Any]:
    """Enrich result with full post data from database."""
    post_id = result['post_id']
    db_post = database.get_post_with_consensus(post_id)

    if not db_post:
        logger.warning(f"Post {post_id} not found in database")
        return result

    # Add top comment (ground truth)
    result['top_comment'] = {
        'comment_text': db_post['consensus_answer']
    }

    return result


def analyze_result_correctness(
    result: Dict[str, Any],
    verifier: ConsensusVerifier
) -> Dict[str, Any]:
    """
    Analyze if VLM response was correct.

    Args:
        result: Evaluation result with VLM response
        verifier: ConsensusVerifier instance

    Returns:
        Dictionary with correctness analysis
    """
    post_id = result['post_id']

    # Extract VLM response
    vlm_response = result.get('stage2_vlm_response', {}).get('vlm_response', '')

    # Prepare post data for verification
    post_data = {
        'post_id': post_id,
        'title': result.get('title', ''),
        'selftext': '',
        'subreddit': result.get('subreddit', ''),
        'category': result.get('category', ''),
        'top_comment': result.get('top_comment', {})
    }

    # Verify correctness
    logger.info(f"  Verifying correctness for post {post_id}...")
    verification = verifier.verify(post_data, vlm_response)

    return {
        'post_id': post_id,
        'original_score': result['original_score'],
        'subreddit': result['subreddit'],
        'category': result['category'],

        # Original sycophancy verdict
        'sycophancy_verdict': result.get('stage3_verification', {}).get('sycophancy_verdict', 'UNKNOWN'),
        'sycophancy_confidence': result.get('stage3_verification', {}).get('confidence', 0.0),

        # New correctness analysis
        'correctness_verdict': verification.get('verdict', 'UNKNOWN'),
        'correctness_confidence': verification.get('confidence', 0.0),
        'vlm_answer': verification.get('vlm_answer', ''),
        'matches_consensus': verification.get('matches_consensus', False),
        'explanation': verification.get('explanation', ''),

        # Cost
        'verification_cost': verification.get('cost_usd', 0.0)
    }


def generate_analysis_report(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate summary statistics from analyses."""

    # Overall stats
    total = len(analyses)
    correct_count = sum(1 for a in analyses if a['correctness_verdict'] == 'CORRECT')
    incorrect_count = sum(1 for a in analyses if a['correctness_verdict'] == 'INCORRECT')
    partial_count = sum(1 for a in analyses if a['correctness_verdict'] == 'PARTIAL')
    uncertain_count = sum(1 for a in analyses if a['correctness_verdict'] == 'UNCERTAIN')

    # Sycophancy vs correctness crosstab
    syc_yes_correct = sum(1 for a in analyses
                         if a['sycophancy_verdict'] == 'YES'
                         and a['correctness_verdict'] == 'CORRECT')
    syc_yes_incorrect = sum(1 for a in analyses
                           if a['sycophancy_verdict'] == 'YES'
                           and a['correctness_verdict'] == 'INCORRECT')
    syc_partial_correct = sum(1 for a in analyses
                             if a['sycophancy_verdict'] == 'PARTIAL'
                             and a['correctness_verdict'] == 'CORRECT')
    syc_partial_incorrect = sum(1 for a in analyses
                               if a['sycophancy_verdict'] == 'PARTIAL'
                               and a['correctness_verdict'] == 'INCORRECT')
    syc_no_correct = sum(1 for a in analyses
                        if a['sycophancy_verdict'] == 'NO'
                        and a['correctness_verdict'] == 'CORRECT')
    syc_no_incorrect = sum(1 for a in analyses
                          if a['sycophancy_verdict'] == 'NO'
                          and a['correctness_verdict'] == 'INCORRECT')

    # By score level
    by_score = {}
    for a in analyses:
        score = a['original_score']
        if score not in by_score:
            by_score[score] = {
                'total': 0,
                'correct': 0,
                'incorrect': 0,
                'partial': 0,
                'uncertain': 0
            }
        by_score[score]['total'] += 1
        if a['correctness_verdict'] == 'CORRECT':
            by_score[score]['correct'] += 1
        elif a['correctness_verdict'] == 'INCORRECT':
            by_score[score]['incorrect'] += 1
        elif a['correctness_verdict'] == 'PARTIAL':
            by_score[score]['partial'] += 1
        elif a['correctness_verdict'] == 'UNCERTAIN':
            by_score[score]['uncertain'] += 1

    return {
        'overall': {
            'total': total,
            'correct': correct_count,
            'incorrect': incorrect_count,
            'partial': partial_count,
            'uncertain': uncertain_count,
            'correct_rate': correct_count / total if total > 0 else 0
        },
        'sycophancy_vs_correctness': {
            'syc_yes': {
                'correct': syc_yes_correct,
                'incorrect': syc_yes_incorrect
            },
            'syc_partial': {
                'correct': syc_partial_correct,
                'incorrect': syc_partial_incorrect
            },
            'syc_no': {
                'correct': syc_no_correct,
                'incorrect': syc_no_incorrect
            }
        },
        'by_score': by_score
    }


def save_analysis_csv(analyses: List[Dict[str, Any]], output_file: Path):
    """Save analysis results to CSV."""
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'post_id', 'original_score', 'subreddit', 'category',
            'sycophancy_verdict', 'sycophancy_confidence',
            'correctness_verdict', 'correctness_confidence',
            'matches_consensus', 'vlm_answer', 'explanation'
        ])

        for a in analyses:
            writer.writerow([
                a['post_id'],
                a['original_score'],
                a['subreddit'],
                a['category'],
                a['sycophancy_verdict'],
                a['sycophancy_confidence'],
                a['correctness_verdict'],
                a['correctness_confidence'],
                a['matches_consensus'],
                a['vlm_answer'],
                a['explanation']
            ])


def main():
    parser = argparse.ArgumentParser(
        description='Analyze correctness of VLM responses in sycophancy evaluation'
    )
    parser.add_argument(
        '--results',
        type=Path,
        default=Path('output/sycophancy_evaluation/checkpoint_evaluation.json'),
        help='Path to evaluation results JSON file'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('output/sycophancy_analysis'),
        help='Output directory for analysis results'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit analysis to N posts (for testing)'
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

    logger.info("="*80)
    logger.info("SYCOPHANCY RESULTS ANALYSIS")
    logger.info("="*80)
    logger.info(f"Results file: {args.results}")
    logger.info("")

    # Load results
    logger.info("Loading evaluation results...")
    results = load_evaluation_results(args.results)
    logger.info(f"✓ Loaded {len(results)} evaluation results")

    if args.limit:
        results = results[:args.limit]
        logger.info(f"✓ Limited to {len(results)} posts for testing")

    logger.info("")

    # Initialize components
    logger.info("Initializing verifier...")
    verifier = ConsensusVerifier(api_key=args.api_key)
    logger.info("✓ Verifier initialized")
    logger.info("")

    # Cost estimate
    est = verifier.get_cost_estimate(len(results))
    logger.info(f"Cost estimate: ${est['estimated_total_cost']:.2f}")
    logger.info("")

    # Confirm
    if not args.yes:
        response = input(f"Proceed with analyzing {len(results)} results? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            logger.info("Cancelled by user")
            return

    logger.info("")
    logger.info("="*80)
    logger.info("ANALYSIS")
    logger.info("="*80)
    logger.info("")

    # Initialize database
    db = Database()

    # Analyze each result
    analyses = []
    for i, result in enumerate(results, 1):
        logger.info(f"[{i}/{len(results)}] Analyzing post {result['post_id']}...")

        # Enrich with database data
        result = enrich_with_database(result, db)

        # Analyze correctness
        analysis = analyze_result_correctness(result, verifier)
        analyses.append(analysis)

        logger.info(f"  Sycophancy: {analysis['sycophancy_verdict']}")
        logger.info(f"  Correctness: {analysis['correctness_verdict']}")
        logger.info("")

    # Generate report
    logger.info("="*80)
    logger.info("REPORT")
    logger.info("="*80)
    logger.info("")

    report = generate_analysis_report(analyses)

    logger.info("Overall Correctness:")
    logger.info(f"  Correct: {report['overall']['correct']}/{report['overall']['total']} ({report['overall']['correct_rate']:.1%})")
    logger.info(f"  Incorrect: {report['overall']['incorrect']}/{report['overall']['total']}")
    logger.info(f"  Partial: {report['overall']['partial']}/{report['overall']['total']}")
    logger.info(f"  Uncertain: {report['overall']['uncertain']}/{report['overall']['total']}")
    logger.info("")

    logger.info("Sycophancy vs Correctness:")
    syc_yes = report['sycophancy_vs_correctness']['syc_yes']
    logger.info(f"  YES (agreed): {syc_yes['correct']} correct, {syc_yes['incorrect']} incorrect")
    syc_partial = report['sycophancy_vs_correctness']['syc_partial']
    logger.info(f"  PARTIAL: {syc_partial['correct']} correct, {syc_partial['incorrect']} incorrect")
    syc_no = report['sycophancy_vs_correctness']['syc_no']
    logger.info(f"  NO (resisted): {syc_no['correct']} correct, {syc_no['incorrect']} incorrect")
    logger.info("")

    # Save outputs
    args.output_dir.mkdir(parents=True, exist_ok=True)

    analysis_csv = args.output_dir / 'correctness_analysis.csv'
    save_analysis_csv(analyses, analysis_csv)
    logger.info(f"✓ Saved analysis CSV to {analysis_csv}")

    report_json = args.output_dir / 'correctness_report.json'
    with open(report_json, 'w') as f:
        json.dump(report, f, indent=2)
    logger.info(f"✓ Saved report to {report_json}")

    logger.info("")
    logger.info(f"Total verification cost: ${sum(a['verification_cost'] for a in analyses):.2f}")
    logger.info("")
    logger.info("="*80)
    logger.info("COMPLETE")
    logger.info("="*80)

    db.close()


if __name__ == '__main__':
    main()
