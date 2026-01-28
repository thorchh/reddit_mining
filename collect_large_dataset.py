#!/usr/bin/env python3
"""
Collect 400+ posts from r/AskDocs for sycophancy research.
Uses multiple time filters to get variety.
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(line_buffering=True)

from collectors.reddit_client import RedditClient
from collectors.post_collector import PostCollector
from storage.database import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def collect_posts_for_timefilter(args):
    """Collect posts for a single time filter."""
    time_filter, limit = args

    try:
        reddit_client = RedditClient()
        db = Database()
        collector = PostCollector(reddit_client, db)

        stats = collector.collect_from_subreddit(
            subreddit_name="AskDocs",
            limit=limit,
            time_filter=time_filter,
            require_images=False
        )

        logger.info(f"[{time_filter}] Collected {stats['posts_collected']} posts")
        return stats

    except Exception as e:
        logger.error(f"[{time_filter}] Error: {e}")
        return {'posts_collected': 0, 'errors': 1}


def export_all_posts(output_path: str) -> list:
    """Export all collected posts to JSON."""
    db = Database()
    posts = db.get_posts_by_subreddit("AskDocs")

    all_posts = []
    seen_ids = set()

    for post in posts:
        if post['id'] in seen_ids:
            continue
        seen_ids.add(post['id'])

        comments = db.get_comments_for_post(post['id'])

        # Top-level comments sorted by score
        top_comments = sorted(
            [c for c in comments if c['depth'] == 0],
            key=lambda x: x['score'],
            reverse=True
        )[:10]

        all_posts.append({
            'id': post['id'],
            'subreddit': post['subreddit'],
            'title': post['title'],
            'selftext': post['selftext'][:5000] if post['selftext'] else '',
            'score': post['score'],
            'num_comments': post['num_comments'],
            'flair': post['link_flair_text'],
            'url': f"https://reddit.com{post['permalink']}",
            'top_comments': [
                {
                    'body': c['body'][:2000],
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

    return all_posts


def find_correction_cases(posts: list) -> list:
    """Find posts where user has wrong belief and physician corrects them."""

    correction_cases = []

    for i, post in enumerate(posts):
        if post.get('flair') != 'Physician Responded':
            continue

        title = post['title'].lower()
        text = (post.get('selftext', '') or '').lower()

        # Get physician comment
        doc_comment = ""
        for c in post.get('top_comments', [])[:3]:
            if c.get('author') != 'AutoModerator' and len(c.get('body', '')) > 50:
                doc_comment = c['body']
                break

        if not doc_comment:
            continue

        doc_lower = doc_comment.lower()

        # USER BELIEF INDICATORS (user thinks something)
        user_belief_score = 0
        user_patterns = [
            ('i think', 1), ('i believe', 1), ('i know', 1),
            ('was wrong', 2), ('was right', 1), ('should have', 1),
            ('misdiagnosed', 2), ('dismissed', 2), ('refused', 2), ('denied', 2),
            ('the doctor was', 1), ('the er was', 1), ('the np was', 1),
            ('am i right', 2), ('am i wrong', 1), ('is this normal', 1),
            ('malpractice', 2), ('report', 1),
        ]

        for pattern, score in user_patterns:
            if pattern in title or pattern in text[:800]:
                user_belief_score += score

        # PHYSICIAN CORRECTION INDICATORS
        doc_correction_score = 0
        doc_patterns = [
            ('no,', 2), ('no.', 2), ('wrong', 2), ('incorrect', 2),
            ('not true', 2), ('not correct', 2), ('actually', 1),
            ('you need to', 1), ('you should', 1), ('go to the er', 2),
            ('unlikely', 1), ('very unlikely', 2), ('not normal', 2),
            ('dumbass', 3), ('pseudoscience', 3), ('not real', 2),
            ('agree with', 1), ('right to', 1), ('correct', 1),
        ]

        for pattern, score in doc_patterns:
            if pattern in doc_lower[:800]:
                doc_correction_score += score

        total_score = user_belief_score + doc_correction_score

        if total_score >= 3:
            correction_cases.append({
                'idx': i,
                'score': total_score,
                'user_score': user_belief_score,
                'doc_score': doc_correction_score,
                'title': post['title'],
                'flair': post['flair'],
                'text': post.get('selftext', '')[:500],
                'doc_response': doc_comment[:600],
                'url': post.get('url', ''),
            })

    correction_cases.sort(key=lambda x: x['score'], reverse=True)
    return correction_cases


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--collect', action='store_true', help='Collect new posts from Reddit')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze existing data')
    args = parser.parse_args()

    output_dir = Path("output/sycophancy_research")
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.collect:
        print("="*70)
        print("COLLECTING 400+ POSTS FROM r/AskDocs")
        print("="*70)

        # Collect from multiple time filters to get variety
        # Reddit API limits to ~100 per time filter
        time_filters = [
            ('week', 100),
            ('month', 150),
            ('year', 150),
            ('all', 100),
        ]

        total_posts = 0
        for time_filter, limit in time_filters:
            print(f"\nCollecting {limit} posts from {time_filter}...")
            stats = collect_posts_for_timefilter((time_filter, limit))
            total_posts += stats.get('posts_collected', 0)

        print(f"\nTotal posts in database: {total_posts}")

    # Export and analyze
    print("\n" + "="*70)
    print("EXPORTING AND ANALYZING POSTS")
    print("="*70)

    output_file = output_dir / f"askdocs_large_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    posts = export_all_posts(str(output_file))

    print(f"\nExported {len(posts)} unique posts to {output_file}")

    # Filter to physician responded
    physician_posts = [p for p in posts if p.get('flair') == 'Physician Responded']
    print(f"Posts with 'Physician Responded' flair: {len(physician_posts)}")

    # Find correction cases
    print("\n" + "="*70)
    print("FINDING CORRECTION CASES")
    print("="*70)

    correction_cases = find_correction_cases(posts)

    print(f"\nFound {len(correction_cases)} potential correction cases (score >= 3)")
    print("\nTop 30 candidates:")

    for case in correction_cases[:30]:
        print(f"\n[{case['idx']}] Score: {case['score']} (user={case['user_score']}, doc={case['doc_score']})")
        print(f"  Title: {case['title'][:65]}")
        print(f"  User: {case['text'][:100]}...")
        print(f"  Doc: {case['doc_response'][:150]}...")

    # Save correction cases
    correction_file = output_dir / f"correction_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(correction_file, 'w') as f:
        json.dump(correction_cases, f, indent=2)

    print(f"\nSaved {len(correction_cases)} correction cases to {correction_file}")


if __name__ == "__main__":
    main()
