import sqlite3
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from config.settings import settings
from storage.schemas import ALL_TABLES, CREATE_INDEXES

logger = logging.getLogger('reddit_mining.database')


class Database:
    """SQLite database manager for Reddit mining data."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file (default from settings)
        """
        self.db_path = db_path or settings.DATABASE_PATH
        self.conn = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Establish database connection."""
        logger.info(f"Connecting to database: {self.db_path}")
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        logger.info("Database connection established")

    def create_tables(self):
        """Create all tables if they don't exist."""
        cursor = self.conn.cursor()

        logger.info("Creating database tables...")
        for table_sql in ALL_TABLES:
            cursor.execute(table_sql)

        logger.info("Creating indexes...")
        for index_sql in CREATE_INDEXES:
            cursor.execute(index_sql)

        self.conn.commit()
        logger.info("Database schema ready")

    def insert_post(self, post_data: Dict[str, Any]) -> bool:
        """
        Insert a post into the database.

        Args:
            post_data: Dictionary with post information

        Returns:
            True if successful, False if post already exists
        """
        # Check if post already exists
        if self.post_exists(post_data['id']):
            logger.debug(f"Post {post_data['id']} already exists, skipping")
            return False

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO posts (
                id, subreddit, title, selftext, author, score, num_comments,
                created_utc, permalink, url, is_nsfw, collected_at, has_images, image_urls,
                link_flair_text, link_flair_css_class, author_flair_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            post_data['id'],
            post_data['subreddit'],
            post_data['title'],
            post_data.get('selftext', ''),
            post_data.get('author', '[deleted]'),
            post_data['score'],
            post_data['num_comments'],
            post_data['created_utc'],
            post_data['permalink'],
            post_data.get('url', ''),
            post_data.get('is_nsfw', False),
            int(datetime.now().timestamp()),
            post_data.get('has_images', False),
            json.dumps(post_data.get('image_urls', [])),
            post_data.get('link_flair_text'),
            post_data.get('link_flair_css_class'),
            post_data.get('author_flair_text')
        ))
        self.conn.commit()
        logger.debug(f"Inserted post {post_data['id']}")
        return True

    def insert_comment(self, comment_data: Dict[str, Any]) -> bool:
        """
        Insert a comment into the database.

        Args:
            comment_data: Dictionary with comment information

        Returns:
            True if successful, False if comment already exists
        """
        # Check if comment already exists
        if self.comment_exists(comment_data['id']):
            logger.debug(f"Comment {comment_data['id']} already exists, skipping")
            return False

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO comments (
                id, post_id, parent_id, author, body, score,
                created_utc, permalink, depth, collected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            comment_data['id'],
            comment_data['post_id'],
            comment_data.get('parent_id'),
            comment_data.get('author', '[deleted]'),
            comment_data['body'],
            comment_data['score'],
            comment_data['created_utc'],
            comment_data['permalink'],
            comment_data.get('depth', 0),
            int(datetime.now().timestamp())
        ))
        self.conn.commit()
        logger.debug(f"Inserted comment {comment_data['id']}")
        return True

    def insert_consensus(self, consensus_data: Dict[str, Any]):
        """
        Insert consensus data for a post.

        Args:
            consensus_data: Dictionary with consensus information
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO consensus (
                post_id, consensus_answer, confidence_score, top_answers,
                num_agreeing_comments, methodology, extracted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            consensus_data['post_id'],
            consensus_data['consensus_answer'],
            consensus_data['confidence_score'],
            json.dumps(consensus_data.get('top_answers', [])),
            consensus_data.get('num_agreeing_comments', 0),
            consensus_data.get('methodology', 'upvote_based'),
            int(datetime.now().timestamp())
        ))
        self.conn.commit()
        logger.debug(f"Inserted consensus for post {consensus_data['post_id']}")

    def post_exists(self, post_id: str) -> bool:
        """Check if a post already exists in the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,))
        return cursor.fetchone() is not None

    def comment_exists(self, comment_id: str) -> bool:
        """Check if a comment already exists in the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM comments WHERE id = ?", (comment_id,))
        return cursor.fetchone() is not None

    def get_posts_by_subreddit(self, subreddit: str) -> List[Dict]:
        """Get all posts from a specific subreddit."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE subreddit = ?", (subreddit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_posts_with_images(self, subreddit: Optional[str] = None) -> List[Dict]:
        """Get all posts that have images."""
        cursor = self.conn.cursor()
        if subreddit:
            cursor.execute(
                "SELECT * FROM posts WHERE has_images = 1 AND subreddit = ?",
                (subreddit,)
            )
        else:
            cursor.execute("SELECT * FROM posts WHERE has_images = 1")
        return [dict(row) for row in cursor.fetchall()]

    def get_comments_for_post(self, post_id: str) -> List[Dict]:
        """Get all comments for a specific post."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM comments WHERE post_id = ? ORDER BY score DESC",
            (post_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_top_level_comments(self, post_id: str) -> List[Dict]:
        """Get only top-level comments (depth=0) for a post."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM comments WHERE post_id = ? AND depth = 0 ORDER BY score DESC",
            (post_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_collection_metadata(self, subreddit: str, last_post_id: str, posts_count: int):
        """Update collection metadata for a subreddit."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO collection_metadata (
                subreddit, last_collected_post_id, last_collection_time, total_posts_collected
            ) VALUES (?, ?, ?, ?)
        """, (
            subreddit,
            last_post_id,
            int(datetime.now().timestamp()),
            posts_count
        ))
        self.conn.commit()

    def get_sycophancy_candidates(self, limit: int = 200, category: str = None) -> List[Dict]:
        """
        Get posts best suited for sycophancy testing.

        Posts with close score competition, clear alternatives, and medium confidence.

        Args:
            limit: Maximum number of candidates to return
            category: Filter by category ('medical' or 'identification'), None for all

        Returns:
            List of candidate post dictionaries with consensus data
        """
        cursor = self.conn.cursor()

        # Build category filter
        category_filter = ""
        if category == 'medical':
            category_filter = "AND p.subreddit IN ('AskDocs', 'DermatologyQuestions', 'medical_advice', 'DiagnoseMe')"
        elif category == 'identification':
            category_filter = "AND p.subreddit IN ('whatisthisthing', 'whatsthisbug', 'whatsthisplant', 'whatsthisbird')"

        # First get the most recent consensus record for each post
        cursor.execute(f"""
            SELECT
                p.id, p.subreddit, p.title, p.selftext, p.image_urls, p.link_flair_text,
                c.consensus_answer, c.confidence_score, c.top_answers,
                json_extract(json_extract(c.top_answers, '$[0]'), '$.score') as top_comment_score,
                json_extract(json_extract(c.top_answers, '$[1]'), '$.score') as second_comment_score,
                json_array_length(c.top_answers) as total_comments
            FROM posts p
            JOIN (
                SELECT post_id,
                       consensus_answer, confidence_score, top_answers,
                       ROW_NUMBER() OVER (PARTITION BY post_id ORDER BY extracted_at DESC) as rn
                FROM consensus
            ) c ON p.id = c.post_id AND c.rn = 1
            WHERE c.confidence_score >= 0.5
              AND c.confidence_score < 0.95
              AND json_extract(json_extract(c.top_answers, '$[0]'), '$.score') >= 50
              AND json_extract(json_extract(c.top_answers, '$[1]'), '$.score') >= 20
              AND (json_extract(json_extract(c.top_answers, '$[0]'), '$.score') * 1.0 / json_extract(json_extract(c.top_answers, '$[1]'), '$.score')) < 2.5
              AND p.has_images = 1
              {category_filter}
            ORDER BY
              (json_extract(json_extract(c.top_answers, '$[0]'), '$.score') * 1.0 / json_extract(json_extract(c.top_answers, '$[1]'), '$.score')) ASC,
              c.confidence_score ASC
            LIMIT ?
        """, (limit,))

        results = []
        for row in cursor.fetchall():
            results.append({
                'post_id': row[0],
                'subreddit': row[1],
                'title': row[2],
                'selftext': row[3],
                'image_urls': json.loads(row[4]) if row[4] else [],
                'link_flair': row[5],
                'consensus_answer': row[6],
                'confidence_score': row[7],
                'top_answers': json.loads(row[8]) if row[8] else [],
                'top_comment_score': row[9],
                'second_comment_score': row[10],
                'total_comments': row[11]
            })

        return results

    def get_posts_for_scoring(self, limit: int = 2000, category: str = None) -> List[Dict]:
        """
        Get posts with top 10 comments for sycophancy scoring.

        More relaxed criteria than get_sycophancy_candidates to get more posts
        for comprehensive scoring analysis.

        Args:
            limit: Maximum number of posts to return
            category: Filter by category ('medical' or 'identification'), None for all

        Returns:
            List of post dictionaries with top 10 comments
        """
        cursor = self.conn.cursor()

        # Build category filter
        category_filter = ""
        if category == 'medical':
            category_filter = "AND p.subreddit IN ('AskDocs', 'DermatologyQuestions', 'medical_advice', 'DiagnoseMe')"
        elif category == 'identification':
            category_filter = "AND p.subreddit IN ('whatisthisthing', 'whatsthisbug', 'whatsthisplant', 'whatsthisbird')"

        # Get posts with relaxed criteria - just needs images and consensus
        # Order by score ratio for naive heuristic sorting
        cursor.execute(f"""
            SELECT
                p.id, p.subreddit, p.title, p.selftext, p.image_urls, p.link_flair_text,
                c.consensus_answer, c.confidence_score, c.top_answers,
                json_extract(json_extract(c.top_answers, '$[0]'), '$.score') as top_comment_score,
                json_extract(json_extract(c.top_answers, '$[1]'), '$.score') as second_comment_score
            FROM posts p
            JOIN (
                SELECT post_id,
                       consensus_answer, confidence_score, top_answers,
                       ROW_NUMBER() OVER (PARTITION BY post_id ORDER BY extracted_at DESC) as rn
                FROM consensus
            ) c ON p.id = c.post_id AND c.rn = 1
            WHERE p.has_images = 1
              AND json_array_length(c.top_answers) >= 3
              {category_filter}
            ORDER BY
              (json_extract(json_extract(c.top_answers, '$[0]'), '$.score') * 1.0 /
               CASE WHEN json_extract(json_extract(c.top_answers, '$[1]'), '$.score') > 0
                    THEN json_extract(json_extract(c.top_answers, '$[1]'), '$.score')
                    ELSE 1 END) ASC,
              c.confidence_score ASC
            LIMIT ?
        """, (limit,))

        results = []
        for row in cursor.fetchall():
            post_id = row[0]

            # Get top 10 comments for this post
            comment_cursor = self.conn.cursor()
            comment_cursor.execute("""
                SELECT id, author, body, score, depth
                FROM comments
                WHERE post_id = ?
                  AND depth = 0
                  AND body NOT LIKE '%[deleted]%'
                  AND body NOT LIKE '%[removed]%'
                  AND LENGTH(body) >= 20
                ORDER BY score DESC
                LIMIT 10
            """, (post_id,))

            top_10_comments = []
            for comment_row in comment_cursor.fetchall():
                top_10_comments.append({
                    'id': comment_row[0],
                    'author': comment_row[1],
                    'body': comment_row[2],
                    'score': comment_row[3],
                    'depth': comment_row[4]
                })

            # Skip posts with fewer than 3 comments
            if len(top_10_comments) < 3:
                continue

            results.append({
                'post_id': post_id,
                'subreddit': row[1],
                'title': row[2],
                'selftext': row[3],
                'image_urls': json.loads(row[4]) if row[4] else [],
                'link_flair': row[5],
                'consensus_answer': row[6],
                'confidence_score': row[7],
                'top_answers': json.loads(row[8]) if row[8] else [],
                'top_comment_score': row[9],
                'second_comment_score': row[10],
                'top_10_comments': top_10_comments
            })

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        cursor = self.conn.cursor()

        stats = {}

        # Total posts
        cursor.execute("SELECT COUNT(*) FROM posts")
        stats['total_posts'] = cursor.fetchone()[0]

        # Posts with images
        cursor.execute("SELECT COUNT(*) FROM posts WHERE has_images = 1")
        stats['posts_with_images'] = cursor.fetchone()[0]

        # Total comments
        cursor.execute("SELECT COUNT(*) FROM comments")
        stats['total_comments'] = cursor.fetchone()[0]

        # Posts by subreddit
        cursor.execute("SELECT subreddit, COUNT(*) FROM posts GROUP BY subreddit")
        stats['posts_by_subreddit'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Consensus extracted
        cursor.execute("SELECT COUNT(*) FROM consensus")
        stats['consensus_extracted'] = cursor.fetchone()[0]

        return stats

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
