#!/usr/bin/env python3
"""
Phase 0: Continuous Reddit data collection from r/AskDocs.

Collects posts + comments, backfills physician flair, then sleeps and repeats.
Designed to run for days on CARC (no GPU needed).

Usage:
    python collect_data.py                      # single pass
    python collect_data.py --continuous          # loop with sleep
    python collect_data.py --continuous --sleep-hours 2
    python collect_data.py --limit 50           # fewer posts per time filter
"""

import sys
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path

import praw
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env.local")
load_dotenv(Path(__file__).parent.parent / ".env")

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, str(Path(__file__).parent.parent))

from collectors.reddit_client import RedditClient
from collectors.post_collector import PostCollector
from storage.database import Database
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"collect_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
    ],
)
logger = logging.getLogger(__name__)


# Time filters to cycle through for variety
TIME_FILTERS = [
    ("week", 100),
    ("month", 150),
    ("year", 200),
    ("all", 150),
]


def collect_one_pass(limit_override: int = None) -> dict:
    """Run one collection pass across all time filters."""
    reddit_client = RedditClient()
    db = Database()
    collector = PostCollector(reddit_client, db)

    stats_before = db.get_statistics()

    total = {"posts": 0, "comments": 0, "errors": 0}

    for time_filter, default_limit in TIME_FILTERS:
        limit = limit_override or default_limit
        logger.info(f"Collecting up to {limit} posts from r/AskDocs ({time_filter})...")

        try:
            stats = collector.collect_from_subreddit(
                subreddit_name="AskDocs",
                limit=limit,
                time_filter=time_filter,
                require_images=False,
            )
            total["posts"] += stats["posts_collected"]
            total["comments"] += stats["comments_collected"]
            total["errors"] += stats["errors"]

            logger.info(
                f"  [{time_filter}] +{stats['posts_collected']} posts, "
                f"+{stats['comments_collected']} comments, "
                f"{stats['posts_skipped']} skipped"
            )
        except Exception as e:
            logger.error(f"  [{time_filter}] Error: {e}")
            total["errors"] += 1

    stats_after = db.get_statistics()
    new_posts = stats_after["total_posts"] - stats_before["total_posts"]
    logger.info(
        f"Pass complete: +{new_posts} new posts in DB "
        f"(total: {stats_after['total_posts']} posts, "
        f"{stats_after['total_comments']} comments)"
    )

    return {"new_posts": new_posts, **total}


def backfill_flair(limit: int = 20):
    """Backfill physician flair for recently collected posts."""
    logger.info(f"Backfilling flair for up to {limit} physician-responded posts...")

    db = Database()
    reddit = praw.Reddit(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_CLIENT_SECRET,
        user_agent=settings.REDDIT_USER_AGENT,
    )

    cursor = db.conn.cursor()
    cursor.execute(
        """SELECT id, title FROM posts
           WHERE link_flair_text = 'Physician Responded'
           ORDER BY collected_at DESC LIMIT ?""",
        (limit,),
    )
    posts = cursor.fetchall()

    total_updated = 0
    for i, (post_id, title) in enumerate(posts):
        # Skip if already backfilled (check if any comment has flair)
        cursor.execute(
            "SELECT COUNT(*) FROM comments WHERE post_id = ? AND author_flair_text IS NOT NULL",
            (post_id,),
        )
        if cursor.fetchone()[0] > 0:
            continue

        try:
            submission = reddit.submission(id=post_id)
            submission.comments.replace_more(limit=0)

            updated = 0
            for comment in submission.comments.list():
                flair = getattr(comment, "author_flair_text", None)
                if flair:
                    cursor.execute(
                        "UPDATE comments SET author_flair_text = ? WHERE id = ?",
                        (flair, comment.id),
                    )
                    if cursor.rowcount > 0:
                        updated += 1

            db.conn.commit()
            total_updated += updated
            if updated > 0:
                logger.info(f"  [{i+1}/{len(posts)}] {title[:50]} — {updated} flairs")

        except Exception as e:
            logger.error(f"  Flair error for {post_id}: {e}")

    logger.info(f"Flair backfill done: {total_updated} comments updated")


def main():
    parser = argparse.ArgumentParser(description="Phase 0: Collect r/AskDocs data")
    parser.add_argument("--continuous", action="store_true", help="Loop forever with sleep between passes")
    parser.add_argument("--sleep-hours", type=float, default=1.0, help="Hours to sleep between passes (default: 1)")
    parser.add_argument("--limit", type=int, default=None, help="Override posts per time filter")
    parser.add_argument("--no-flair", action="store_true", help="Skip flair backfill")
    parser.add_argument("--max-passes", type=int, default=None, help="Stop after N passes")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("PHASE 0: REDDIT DATA COLLECTION")
    logger.info(f"  Mode: {'continuous' if args.continuous else 'single pass'}")
    logger.info(f"  Limit: {args.limit or 'default per time filter'}")
    logger.info("=" * 60)

    pass_num = 0
    zero_new_streak = 0

    while True:
        pass_num += 1
        logger.info(f"\n--- Pass {pass_num} ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ---")

        result = collect_one_pass(args.limit)

        if not args.no_flair:
            backfill_flair()

        if result["new_posts"] == 0:
            zero_new_streak += 1
            logger.info(f"No new posts ({zero_new_streak} passes in a row)")
        else:
            zero_new_streak = 0

        if not args.continuous:
            break

        if args.max_passes and pass_num >= args.max_passes:
            logger.info(f"Reached max passes ({args.max_passes}). Stopping.")
            break

        if zero_new_streak >= 5:
            logger.info("5 consecutive passes with no new posts. Stopping.")
            break

        sleep_secs = args.sleep_hours * 3600
        logger.info(f"Sleeping {args.sleep_hours}h until next pass...")
        time.sleep(sleep_secs)

    logger.info("Collection finished.")


if __name__ == "__main__":
    main()
