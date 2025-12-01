import logging
from typing import Dict, List, Any, Optional
import json

from storage.database import Database

logger = logging.getLogger('reddit_mining.consensus')


class ConsensusExtractor:
    """Extract consensus answers from Reddit comments using upvote-based ranking."""

    def __init__(self, database: Database):
        """
        Initialize consensus extractor.

        Args:
            database: Database instance
        """
        self.db = database

    def extract_consensus_for_post(self, post_id: str, min_score: int = 5) -> Optional[Dict[str, Any]]:
        """
        Extract consensus answer for a single post.

        Args:
            post_id: Post ID to extract consensus for
            min_score: Minimum score for top comment to be considered valid

        Returns:
            Dictionary with consensus data, or None if no valid consensus
        """
        # Get top-level comments, sorted by score
        comments = self.db.get_top_level_comments(post_id)

        if not comments:
            logger.debug(f"No comments found for post {post_id}")
            return None

        # Calculate consensus using simple upvote-based ranking
        consensus_data = self._calculate_consensus(comments, min_score)

        if consensus_data:
            consensus_data['post_id'] = post_id
            consensus_data['methodology'] = 'upvote_based'
            return consensus_data

        return None

    def _calculate_consensus(self, comments: List[Dict], min_score: int = 5) -> Optional[Dict[str, Any]]:
        """
        Calculate consensus from comment list using upvote ranking.

        Args:
            comments: List of comment dictionaries (sorted by score DESC)
            min_score: Minimum score threshold for valid consensus

        Returns:
            Dictionary with consensus data
        """
        if not comments:
            return None

        # Get top comments
        top_comment = comments[0]
        second_comment = comments[1] if len(comments) > 1 else None
        third_comment = comments[2] if len(comments) > 2 else None

        top_score = top_comment['score']

        # Check minimum score threshold
        if top_score < min_score:
            logger.debug(f"Top comment score ({top_score}) below threshold ({min_score})")
            return {
                'consensus_answer': top_comment['body'],
                'confidence_score': 0.0,
                'top_answers': self._format_top_answers(comments[:3]),
                'num_agreeing_comments': 1,
                'confidence_level': 'none',
                'reason': f'Top comment score ({top_score}) below minimum threshold ({min_score})'
            }

        # Calculate confidence score
        second_score = second_comment['score'] if second_comment else 0
        total_score = top_score + second_score + 1  # +1 to avoid division by zero

        # Confidence formula: top_score / (top_score + second_score + 1)
        raw_confidence = min(1.0, top_score / total_score)

        # Adjust confidence based on score ratio
        if second_score == 0 or top_score > (2 * second_score):
            # Clear winner: high confidence
            confidence_score = min(1.0, raw_confidence * 1.2)
            confidence_level = 'high'
        elif top_score > (1.5 * second_score):
            # Moderate lead: medium confidence
            confidence_score = raw_confidence
            confidence_level = 'medium'
        else:
            # Close competition: low confidence
            confidence_score = raw_confidence * 0.7
            confidence_level = 'low'

        # Ensure confidence is in [0, 1]
        confidence_score = max(0.0, min(1.0, confidence_score))

        return {
            'consensus_answer': top_comment['body'],
            'confidence_score': round(confidence_score, 3),
            'confidence_level': confidence_level,
            'top_answers': self._format_top_answers(comments[:5]),
            'num_agreeing_comments': len([c for c in comments if c['score'] >= top_score * 0.5]),
            'top_comment_score': top_score,
            'second_comment_score': second_score,
            'total_comments': len(comments)
        }

    def _format_top_answers(self, comments: List[Dict]) -> List[Dict[str, Any]]:
        """
        Format top answers for storage.

        Args:
            comments: List of comment dictionaries

        Returns:
            List of formatted answer dictionaries
        """
        answers = []
        for i, comment in enumerate(comments):
            answers.append({
                'rank': i + 1,
                'answer': comment['body'][:200],  # Truncate to 200 chars
                'score': comment['score'],
                'author': comment['author'],
                'comment_id': comment['id']
            })
        return answers

    def extract_consensus_for_all_posts(self, subreddit: Optional[str] = None) -> Dict[str, int]:
        """
        Extract consensus for all posts in the database (or for a specific subreddit).

        Args:
            subreddit: Optional subreddit filter

        Returns:
            Dictionary with processing statistics
        """
        logger.info("Starting consensus extraction for all posts...")

        # Get all posts with images
        if subreddit:
            posts = self.db.get_posts_with_images(subreddit=subreddit)
            logger.info(f"Found {len(posts)} posts with images in r/{subreddit}")
        else:
            posts = self.db.get_posts_with_images()
            logger.info(f"Found {len(posts)} posts with images across all subreddits")

        stats = {
            'total_posts': len(posts),
            'consensus_extracted': 0,
            'no_consensus': 0,
            'errors': 0
        }

        for i, post in enumerate(posts):
            post_id = post['id']
            logger.info(f"[{i+1}/{len(posts)}] Extracting consensus for post {post_id}...")

            try:
                consensus_data = self.extract_consensus_for_post(post_id)

                if consensus_data:
                    self.db.insert_consensus(consensus_data)
                    stats['consensus_extracted'] += 1
                    logger.info(
                        f"✓ Consensus: '{consensus_data['consensus_answer'][:50]}...' "
                        f"(confidence: {consensus_data['confidence_score']:.2f})"
                    )
                else:
                    stats['no_consensus'] += 1
                    logger.warning(f"✗ No valid consensus found for post {post_id}")

            except Exception as e:
                logger.error(f"Error extracting consensus for post {post_id}: {e}")
                stats['errors'] += 1

        logger.info(f"\nConsensus extraction complete: {stats}")
        return stats

    def export_dataset(self, output_path: str, min_confidence: float = 0.0):
        """
        Export dataset to JSONL format for model evaluation.

        Args:
            output_path: Path to output JSONL file
            min_confidence: Minimum confidence threshold for inclusion
        """
        logger.info(f"Exporting dataset to {output_path}...")

        # Get all posts with consensus
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT
                p.id as post_id,
                p.subreddit,
                p.title,
                p.selftext,
                p.image_urls,
                p.is_nsfw,
                c.consensus_answer,
                c.confidence_score,
                c.top_answers
            FROM posts p
            JOIN consensus c ON p.id = c.post_id
            WHERE c.confidence_score >= ?
            ORDER BY c.confidence_score DESC
        """, (min_confidence,))

        rows = cursor.fetchall()
        logger.info(f"Found {len(rows)} posts with consensus >= {min_confidence}")

        with open(output_path, 'w') as f:
            for row in rows:
                # Parse JSON fields
                image_urls = json.loads(row[4]) if row[4] else []
                top_answers = json.loads(row[8]) if row[8] else []

                # Create dataset entry
                entry = {
                    'post_id': row[0],
                    'subreddit': row[1],
                    'question': row[2],  # title
                    'context': row[3],   # selftext
                    'image_urls': image_urls,
                    'is_nsfw': bool(row[5]),
                    'consensus_answer': row[6],
                    'confidence': row[7],
                    'alternative_answers': top_answers[1:] if len(top_answers) > 1 else []
                }

                # Write as JSONL
                f.write(json.dumps(entry) + '\n')

        logger.info(f"Dataset exported to {output_path}")
