#!/usr/bin/env python3
"""
Collect historical r/AskDocs posts and comments from Arctic Shift API.

Downloads "Physician Responded" posts and their comments, then inserts
them into the same SQLite database used by the rest of the pipeline.

Usage:
    python collect_arctic_shift.py --months 3          # last 3 months of 2024
    python collect_arctic_shift.py --after 2024-01-01 --before 2024-04-01
    python collect_arctic_shift.py --after 2023-01-01 --before 2024-01-01
    python collect_arctic_shift.py --count-only         # just show counts per year
"""

import sys
import json
import time
import argparse
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.database import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://arctic-shift.photon-reddit.com"


def count_posts_per_year():
    """Show how many Physician Responded posts exist per year."""
    print("\nCounting 'Physician Responded' posts on r/AskDocs by year...\n")

    # Query in chunks to avoid timeouts
    ranges = [
        ("2017-01-01", "2020-01-01"),
        ("2020-01-01", "2023-01-01"),
        ("2023-01-01", "2027-01-01"),
    ]

    for start, end in ranges:
        try:
            resp = requests.get(f"{BASE_URL}/api/posts/search/aggregate", params={
                "subreddit": "AskDocs",
                "link_flair_text": "Physician Responded",
                "aggregate": "created_utc",
                "frequency": "year",
                "after": start,
                "before": end,
            }, timeout=30)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            for entry in data:
                year = entry.get("created_utc", "")[:4] if isinstance(entry.get("created_utc"), str) else "?"
                count = entry.get("count", entry.get("doc_count", 0))
                print(f"  {year}: {count:,} posts")
        except requests.HTTPError as e:
            print(f"  Error for {start}-{end}: {e}")
            print(f"  Response: {e.response.text[:300]}")
        except Exception as e:
            print(f"  Error for {start}-{end}: {e}")

        time.sleep(0.5)


def fetch_posts(after: str, before: str) -> list:
    """Fetch all Physician Responded posts in a date range from Arctic Shift."""
    all_posts = []
    cursor = after

    while True:
        params = {
            "subreddit": "AskDocs",
            "link_flair_text": "Physician Responded",
            "sort": "asc",
            "after": cursor,
            "before": before,
            "limit": 100,
        }

        try:
            resp = requests.get(f"{BASE_URL}/api/posts/search", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except Exception as e:
            logger.error(f"Error fetching posts: {e}")
            time.sleep(2)
            continue

        if not data:
            break

        all_posts.extend(data)
        # Move cursor past last result
        cursor = str(data[-1]["created_utc"])

        if len(all_posts) % 500 == 0 or len(data) < 100:
            logger.info(f"  Fetched {len(all_posts)} posts so far...")

        time.sleep(0.3)

    return all_posts


def fetch_comments_for_post(post_id: str) -> list:
    """Fetch all comments for a post from Arctic Shift."""
    all_comments = []
    cursor = None

    while True:
        params = {
            "link_id": post_id,
            "limit": 100,
        }
        if cursor:
            params["after"] = cursor

        try:
            resp = requests.get(f"{BASE_URL}/api/comments/search", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except Exception as e:
            logger.error(f"Error fetching comments for {post_id}: {e}")
            return all_comments

        if not data:
            break

        all_comments.extend(data)
        cursor = str(data[-1]["created_utc"])

        if len(data) < 100:
            break

        time.sleep(0.2)

    return all_comments


def insert_arctic_post(db: Database, post: dict) -> bool:
    """Insert an Arctic Shift post into the database."""
    post_data = {
        "id": post.get("id", ""),
        "subreddit": post.get("subreddit", "AskDocs"),
        "title": post.get("title", ""),
        "selftext": post.get("selftext", ""),
        "author": post.get("author", "[deleted]"),
        "score": post.get("score", 0),
        "num_comments": post.get("num_comments", 0),
        "created_utc": post.get("created_utc", 0),
        "permalink": post.get("permalink", ""),
        "url": post.get("url", ""),
        "is_nsfw": post.get("over_18", False),
        "has_images": False,
        "image_urls": [],
        "link_flair_text": post.get("link_flair_text", ""),
        "link_flair_css_class": post.get("link_flair_css_class", ""),
        "author_flair_text": post.get("author_flair_text", ""),
    }
    return db.insert_post(post_data)


def insert_arctic_comment(db: Database, comment: dict, post_id: str) -> bool:
    """Insert an Arctic Shift comment into the database."""
    # Calculate depth from parent_id
    parent_id = comment.get("parent_id", "")
    depth = 0 if not parent_id or not parent_id.startswith("t1_") else 1

    comment_data = {
        "id": comment.get("id", ""),
        "post_id": post_id,
        "parent_id": parent_id,
        "author": comment.get("author", "[deleted]"),
        "body": comment.get("body", ""),
        "score": comment.get("score", 0),
        "created_utc": comment.get("created_utc", 0),
        "permalink": comment.get("permalink", ""),
        "depth": depth,
        "author_flair_text": comment.get("author_flair_text"),
    }
    return db.insert_comment(comment_data)


def main():
    parser = argparse.ArgumentParser(description="Collect historical r/AskDocs data from Arctic Shift")
    parser.add_argument("--after", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--before", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--months", type=int, default=None, help="Collect last N months of 2024")
    parser.add_argument("--count-only", action="store_true", help="Just show post counts per year")
    parser.add_argument("--skip-comments", action="store_true", help="Only download posts, skip comments")
    parser.add_argument("--comment-workers", type=int, default=5, help="Parallel comment fetchers")
    args = parser.parse_args()

    if args.count_only:
        count_posts_per_year()
        return

    # Determine date range
    if args.months:
        before_dt = datetime(2025, 1, 1)
        after_dt = before_dt - timedelta(days=args.months * 30)
        after = after_dt.strftime("%Y-%m-%d")
        before = before_dt.strftime("%Y-%m-%d")
    elif args.after and args.before:
        after = args.after
        before = args.before
    else:
        print("Specify --after/--before or --months. Use --count-only to see available data.")
        sys.exit(1)

    logger.info(f"Collecting r/AskDocs 'Physician Responded' posts: {after} to {before}")

    # Fetch posts
    logger.info("Fetching posts from Arctic Shift...")
    posts = fetch_posts(after, before)
    logger.info(f"Found {len(posts)} posts")

    if not posts:
        logger.info("No posts found.")
        return

    # Insert posts into database
    db = Database()
    new_posts = 0
    skipped_posts = 0
    posts_for_comments = []

    for post in posts:
        selftext = post.get("selftext", "") or ""
        if selftext in ("[removed]", "[deleted]", ""):
            skipped_posts += 1
            continue

        if insert_arctic_post(db, post):
            new_posts += 1
            posts_for_comments.append(post)
        else:
            skipped_posts += 1

    logger.info(f"Posts: {new_posts} new, {skipped_posts} skipped (already in DB or empty)")

    # Fetch comments
    if not args.skip_comments and posts_for_comments:
        logger.info(f"\nFetching comments for {len(posts_for_comments)} new posts...")
        total_comments = 0
        done = 0

        with ThreadPoolExecutor(max_workers=args.comment_workers) as executor:
            futures = {
                executor.submit(fetch_comments_for_post, p["id"]): p["id"]
                for p in posts_for_comments
            }

            for future in as_completed(futures):
                post_id = futures[future]
                done += 1
                try:
                    comments = future.result()
                    for c in comments:
                        body = c.get("body", "")
                        if body in ("[removed]", "[deleted]", ""):
                            continue
                        if insert_arctic_comment(db, c, post_id):
                            total_comments += 1
                except Exception as e:
                    logger.error(f"Error processing comments for {post_id}: {e}")

                if done % 100 == 0:
                    logger.info(f"  Comments: {done}/{len(posts_for_comments)} posts processed, {total_comments} comments added")

        logger.info(f"Comments: {total_comments} new comments added")

    # Final stats
    stats = db.get_statistics()
    logger.info(f"\nDatabase totals: {stats['total_posts']} posts, {stats['total_comments']} comments")


if __name__ == "__main__":
    main()
