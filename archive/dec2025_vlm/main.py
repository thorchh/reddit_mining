#!/usr/bin/env python3
"""
Reddit Mining Pipeline for VLM Sycophancy Research

Main script to collect posts and comments from medical and identification subreddits.
"""

import argparse
import yaml
import logging
from pathlib import Path

from collectors.reddit_client import RedditClient
from collectors.post_collector import PostCollector
from storage.database import Database
from utils.logger import setup_logger
from config.settings import settings

logger = setup_logger('reddit_mining', level=logging.INFO)


def load_subreddit_config(config_path: str = 'config/subreddits.yaml') -> dict:
    """Load subreddit configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def collect_from_all_subreddits(
    subreddit_config: dict,
    posts_per_subreddit: int = 150,
    categories: list = None,
    require_images: bool = True
):
    """
    Collect data from all configured subreddits.

    Args:
        subreddit_config: Dictionary with subreddit configuration
        posts_per_subreddit: Number of posts to collect per subreddit
        categories: List of categories to collect from (None = all)
        require_images: Whether to require posts to have images
    """
    # Initialize clients
    logger.info("Initializing Reddit client and database...")
    reddit_client = RedditClient()
    db = Database()
    collector = PostCollector(reddit_client, db)

    # Determine which categories to collect from
    if categories is None:
        categories = list(subreddit_config.keys())

    total_stats = {
        'posts_collected': 0,
        'posts_skipped': 0,
        'comments_collected': 0,
        'errors': 0,
        'subreddits_processed': 0
    }

    # Collect from each category and subreddit
    for category in categories:
        if category not in subreddit_config:
            logger.warning(f"Category '{category}' not found in config, skipping")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"Processing category: {category.upper()}")
        logger.info(f"{'='*60}\n")

        subreddits = subreddit_config[category]

        for sub_info in subreddits:
            subreddit_name = sub_info['name']
            description = sub_info.get('description', '')

            logger.info(f"\n--- Collecting from r/{subreddit_name} ---")
            logger.info(f"Description: {description}")

            try:
                stats = collector.collect_from_subreddit(
                    subreddit_name=subreddit_name,
                    limit=posts_per_subreddit,
                    time_filter='year',
                    require_images=require_images
                )

                # Update total stats
                total_stats['posts_collected'] += stats['posts_collected']
                total_stats['posts_skipped'] += stats['posts_skipped']
                total_stats['comments_collected'] += stats['comments_collected']
                total_stats['errors'] += stats['errors']
                total_stats['subreddits_processed'] += 1

                logger.info(f"✓ Completed r/{subreddit_name}: {stats}")

            except Exception as e:
                logger.error(f"✗ Failed to collect from r/{subreddit_name}: {e}")
                total_stats['errors'] += 1

    # Print final statistics
    logger.info(f"\n{'='*60}")
    logger.info("COLLECTION COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Subreddits processed: {total_stats['subreddits_processed']}")
    logger.info(f"Posts collected: {total_stats['posts_collected']}")
    logger.info(f"Posts skipped: {total_stats['posts_skipped']}")
    logger.info(f"Comments collected: {total_stats['comments_collected']}")
    logger.info(f"Errors: {total_stats['errors']}")

    # Database statistics
    db_stats = db.get_statistics()
    logger.info(f"\n{'='*60}")
    logger.info("DATABASE STATISTICS")
    logger.info(f"{'='*60}")
    logger.info(f"Total posts: {db_stats['total_posts']}")
    logger.info(f"Posts with images: {db_stats['posts_with_images']}")
    logger.info(f"Total comments: {db_stats['total_comments']}")
    logger.info(f"\nPosts by subreddit:")
    for subreddit, count in db_stats['posts_by_subreddit'].items():
        logger.info(f"  r/{subreddit}: {count}")

    # Close database
    db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Reddit Mining Pipeline for VLM Sycophancy Research'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/subreddits.yaml',
        help='Path to subreddit configuration file'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=150,
        help='Number of posts to collect per subreddit (default: 150)'
    )
    parser.add_argument(
        '--categories',
        type=str,
        nargs='+',
        choices=['medical', 'identification'],
        help='Categories to collect from (default: all)'
    )
    parser.add_argument(
        '--no-images',
        action='store_true',
        help='Don\'t require posts to have images'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: only collect from one subreddit'
    )

    args = parser.parse_args()

    try:
        # Load configuration
        logger.info("Loading subreddit configuration...")
        config = load_subreddit_config(args.config)

        if args.test:
            logger.info("TEST MODE: Collecting from r/whatisthisthing only")
            test_config = {'identification': [{'name': 'whatisthisthing', 'description': 'Test subreddit'}]}
            collect_from_all_subreddits(
                subreddit_config=test_config,
                posts_per_subreddit=10,
                require_images=not args.no_images
            )
        else:
            # Full collection
            collect_from_all_subreddits(
                subreddit_config=config,
                posts_per_subreddit=args.limit,
                categories=args.categories,
                require_images=not args.no_images
            )

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
