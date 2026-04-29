#!/usr/bin/env python3
"""Backfill author_flair_text for existing comments from Reddit API."""

import sys
import praw
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from storage.database import Database

def main():
    db = Database()
    reddit = praw.Reddit(
        client_id="URqEYXro0q5QD6rEHm-KFw",
        client_secret="wCKf921y2yOEMwgk0Kp786qP6eIEQQ",
        user_agent="reddit_mining:v1.0.0 (by /u/Senior_Page_3289)",
    )

    cursor = db.conn.cursor()

    # If --screening flag, load post IDs from screening JSON
    if len(sys.argv) > 1 and sys.argv[1] == "--screening":
        import json
        screening_file = sys.argv[2] if len(sys.argv) > 2 else "output/sycophancy_research/screening_20260204_145819.json"
        cases = json.load(open(screening_file))
        post_ids = [c["post_id"] for c in cases]
        placeholders = ",".join("?" * len(post_ids))
        cursor.execute(
            f"SELECT id, title FROM posts WHERE id IN ({placeholders})", post_ids
        )
    else:
        limit = int(sys.argv[1]) if len(sys.argv) > 1 else 3
        cursor.execute(
            "SELECT id, title FROM posts WHERE link_flair_text = 'Physician Responded' LIMIT ?",
            (limit,),
        )
    posts = cursor.fetchall()
    print(f"Backfilling flair for {len(posts)} posts...")

    total_updated = 0
    for i, (post_id, title) in enumerate(posts):
        print(f"\n[{i+1}/{len(posts)}] {title[:60]}")
        try:
            submission = reddit.submission(id=post_id)
            submission.comments.replace_more(limit=0)

            updated = 0
            for comment in submission.comments.list():
                flair = comment.author_flair_text if hasattr(comment, 'author_flair_text') else None
                if flair:
                    cursor.execute(
                        "UPDATE comments SET author_flair_text = ? WHERE id = ?",
                        (flair, comment.id),
                    )
                    if cursor.rowcount > 0:
                        updated += 1
                        print(f"  {comment.author}: [{flair}]")

            db.conn.commit()
            total_updated += updated
            print(f"  Updated {updated} comments with flair")

        except Exception as e:
            print(f"  Error: {e}")

    print(f"\nDone. Updated {total_updated} comments total.")


if __name__ == "__main__":
    main()
