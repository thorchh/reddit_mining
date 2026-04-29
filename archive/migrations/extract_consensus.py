#!/usr/bin/env python3
"""
Consensus Extraction Script

Extract consensus answers from collected Reddit comments and export dataset.
"""

import argparse
import logging

from storage.database import Database
from processors.consensus_extractor import ConsensusExtractor
from utils.logger import setup_logger

logger = setup_logger('consensus_extraction', level=logging.INFO)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Extract consensus from Reddit comments'
    )
    parser.add_argument(
        '--subreddit',
        type=str,
        help='Extract consensus for specific subreddit only'
    )
    parser.add_argument(
        '--export',
        type=str,
        default='dataset.jsonl',
        help='Path to export dataset (default: dataset.jsonl)'
    )
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.4,
        help='Minimum confidence threshold for export (default: 0.4)'
    )
    parser.add_argument(
        '--skip-extraction',
        action='store_true',
        help='Skip consensus extraction, only export existing data'
    )

    args = parser.parse_args()

    try:
        # Initialize database and extractor
        logger.info("Initializing database and consensus extractor...")
        db = Database()
        extractor = ConsensusExtractor(db)

        # Extract consensus
        if not args.skip_extraction:
            logger.info("\n" + "="*60)
            logger.info("EXTRACTING CONSENSUS")
            logger.info("="*60 + "\n")

            stats = extractor.extract_consensus_for_all_posts(
                subreddit=args.subreddit
            )

            logger.info(f"\nConsensus extraction statistics:")
            logger.info(f"  Total posts: {stats['total_posts']}")
            logger.info(f"  Consensus extracted: {stats['consensus_extracted']}")
            logger.info(f"  No consensus: {stats['no_consensus']}")
            logger.info(f"  Errors: {stats['errors']}")

        # Export dataset
        logger.info("\n" + "="*60)
        logger.info("EXPORTING DATASET")
        logger.info("="*60 + "\n")

        extractor.export_dataset(
            output_path=args.export,
            min_confidence=args.min_confidence
        )

        logger.info(f"\n✓ Dataset exported to: {args.export}")
        logger.info(f"  Minimum confidence: {args.min_confidence}")

        # Close database
        db.close()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
