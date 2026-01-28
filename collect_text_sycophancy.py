#!/usr/bin/env python3
"""
Collect text-only posts from r/AskDocs for sycophancy analysis.

Pattern: patient has health belief/concern → asks for validation →
sycophantic response agrees vs provides accurate medical guidance.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from collectors.reddit_client import RedditClient
from collectors.post_collector import PostCollector
from storage.database import Database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Target subreddit
TARGET_SUBREDDITS = ["AskDocs"]


def collect_text_posts(
    subreddits: list[str],
    posts_per_sub: int = 50,
    time_filter: str = "month"
) -> dict:
    """
    Collect text-only posts from specified subreddits.
    """
    reddit_client = RedditClient()
    db = Database()
    collector = PostCollector(reddit_client, db)

    total_stats = {
        'subreddits_collected': 0,
        'total_posts': 0,
        'total_comments': 0,
        'errors': 0
    }

    for subreddit in subreddits:
        logger.info(f"\n{'='*50}")
        logger.info(f"Collecting from r/{subreddit}")
        logger.info(f"{'='*50}")

        try:
            stats = collector.collect_from_subreddit(
                subreddit_name=subreddit,
                limit=posts_per_sub,
                time_filter=time_filter,
                require_images=False  # Text-only
            )

            total_stats['subreddits_collected'] += 1
            total_stats['total_posts'] += stats['posts_collected']
            total_stats['total_comments'] += stats['comments_collected']
            total_stats['errors'] += stats['errors']

        except Exception as e:
            logger.error(f"Failed to collect from r/{subreddit}: {e}")
            total_stats['errors'] += 1

    return total_stats


def export_collected_posts(subreddits: list[str], output_path: str) -> int:
    """
    Export collected posts to JSON for review.
    """
    db = Database()
    all_posts = []

    for subreddit in subreddits:
        posts = db.get_posts_by_subreddit(subreddit)

        for post in posts:
            comments = db.get_comments_for_post(post['id'])

            # Top-level comments only, sorted by score
            top_comments = sorted(
                [c for c in comments if c['depth'] == 0],
                key=lambda x: x['score'],
                reverse=True
            )[:10]

            all_posts.append({
                'id': post['id'],
                'subreddit': post['subreddit'],
                'title': post['title'],
                'selftext': post['selftext'][:3000] if post['selftext'] else '',
                'score': post['score'],
                'num_comments': post['num_comments'],
                'flair': post['link_flair_text'],
                'url': f"https://reddit.com{post['permalink']}",
                'top_comments': [
                    {
                        'body': c['body'][:1000],
                        'score': c['score'],
                        'author': c['author']
                    }
                    for c in top_comments
                ]
            })

    all_posts.sort(key=lambda x: x['score'], reverse=True)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, 'w') as f:
        json.dump(all_posts, f, indent=2)

    logger.info(f"Exported {len(all_posts)} posts to {output_path}")
    return len(all_posts)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Collect AskDocs posts for sycophancy analysis')
    parser.add_argument('--posts', type=int, default=50, help='Posts to collect')
    parser.add_argument('--time', default='month', choices=['day', 'week', 'month', 'year', 'all'])
    parser.add_argument('--export-only', action='store_true', help='Only export existing data')
    parser.add_argument('--subreddits', nargs='+', default=TARGET_SUBREDDITS)
    args = parser.parse_args()

    output_dir = Path(__file__).parent / "output" / "text_sycophancy"
    output_file = output_dir / f"askdocs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    if not args.export_only:
        logger.info("Starting AskDocs text post collection...")
        logger.info(f"Posts: {args.posts}, Time filter: {args.time}")

        stats = collect_text_posts(
            subreddits=args.subreddits,
            posts_per_sub=args.posts,
            time_filter=args.time
        )

        logger.info(f"\nCOLLECTION COMPLETE")
        logger.info(f"Posts: {stats['total_posts']}, Comments: {stats['total_comments']}")

    logger.info("\nExporting posts for review...")
    export_collected_posts(args.subreddits, str(output_file))

    print(f"\n✓ Posts exported to: {output_file}")


if __name__ == "__main__":
    main()
