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
        self.conn = sqlite3.connect(self.db_path)
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
                created_utc, permalink, url, is_nsfw, collected_at, has_images, image_urls
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            json.dumps(post_data.get('image_urls', []))
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
