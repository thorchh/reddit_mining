import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import praw

from collectors.reddit_client import RedditClient
from storage.database import Database
from config.settings import settings

logger = logging.getLogger('reddit_mining.collector')


class PostCollector:
    """Collects posts and comments from Reddit subreddits."""

    def __init__(self, reddit_client: RedditClient, database: Database):
        """
        Initialize post collector.

        Args:
            reddit_client: RedditClient instance
            database: Database instance
        """
        self.client = reddit_client
        self.db = database

    def collect_from_subreddit(
        self,
        subreddit_name: str,
        limit: int = 150,
        time_filter: str = 'year',
        require_images: bool = False
    ) -> Dict[str, int]:
        """
        Collect posts and comments from a subreddit.

        Args:
            subreddit_name: Name of the subreddit to collect from
            limit: Maximum number of posts to collect
            time_filter: Time filter for top posts ('year', 'month', 'week', 'day', 'all')
            require_images: If True, only collect posts with images

        Returns:
            Dictionary with collection statistics
        """
        logger.info(f"Starting collection from r/{subreddit_name}")
        logger.info(f"Settings: limit={limit}, time_filter={time_filter}, require_images={require_images}")

        stats = {
            'posts_collected': 0,
            'posts_skipped': 0,
            'comments_collected': 0,
            'errors': 0
        }

        try:
            posts = self.client.get_top_posts(
                subreddit_name=subreddit_name,
                time_filter=time_filter,
                limit=limit * 2  # Fetch more since we'll filter
            )

            for submission in posts:
                try:
                    # Check if we've reached our limit
                    if stats['posts_collected'] >= limit:
                        logger.info(f"Reached collection limit of {limit} posts")
                        break

                    # Apply filters
                    if not self._should_collect_post(submission, require_images):
                        stats['posts_skipped'] += 1
                        continue

                    # Extract post data
                    post_data = self._extract_post_data(submission)

                    # Insert post
                    if self.db.insert_post(post_data):
                        stats['posts_collected'] += 1
                        logger.info(
                            f"[{stats['posts_collected']}/{limit}] "
                            f"Collected post: {submission.id} - {submission.title[:50]}..."
                        )

                        # Collect comments for this post
                        comment_count = self._collect_comments(submission)
                        stats['comments_collected'] += comment_count
                    else:
                        stats['posts_skipped'] += 1

                except Exception as e:
                    logger.error(f"Error collecting post {submission.id}: {e}")
                    stats['errors'] += 1
                    continue

            # Update metadata
            if stats['posts_collected'] > 0:
                self.db.update_collection_metadata(
                    subreddit=subreddit_name,
                    last_post_id=submission.id if submission else None,
                    posts_count=stats['posts_collected']
                )

        except Exception as e:
            logger.error(f"Error collecting from r/{subreddit_name}: {e}")
            stats['errors'] += 1

        logger.info(f"Collection complete for r/{subreddit_name}: {stats}")
        return stats

    def _should_collect_post(self, submission, require_images: bool = False) -> bool:
        """
        Check if a post meets collection criteria.

        Args:
            submission: PRAW submission object
            require_images: Whether to require images

        Returns:
            True if post should be collected
        """
        # Check if post is deleted or removed
        if submission.selftext == '[removed]' or submission.selftext == '[deleted]':
            return False

        # Check minimum comment count
        if submission.num_comments < settings.MIN_COMMENTS:
            return False

        # Check minimum score
        if submission.score < settings.MIN_POST_SCORE:
            return False

        # Check age
        post_age_days = (datetime.now() - datetime.fromtimestamp(submission.created_utc)).days
        if post_age_days > settings.MAX_POST_AGE_DAYS:
            return False

        # Check for images if required
        if require_images:
            has_images = self._check_has_images(submission)
            if not has_images:
                return False

        return True

    def _check_has_images(self, submission) -> bool:
        """
        Check if a submission has images.

        Args:
            submission: PRAW submission object

        Returns:
            True if submission has images
        """
        # Check URL for image extensions
        if hasattr(submission, 'url'):
            url = submission.url.lower()
            if any(url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                return True

            # Check for image hosts
            if 'i.redd.it' in url or 'imgur.com' in url:
                return True

        # Check for gallery
        if hasattr(submission, 'is_gallery') and submission.is_gallery:
            return True

        return False

    def _extract_image_urls(self, submission) -> List[str]:
        """
        Extract all image URLs from a submission.

        Args:
            submission: PRAW submission object

        Returns:
            List of image URLs
        """
        urls = []

        # Direct image URL
        if hasattr(submission, 'url'):
            url = submission.url
            if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                urls.append(url)
            elif 'i.redd.it' in url or 'imgur.com/a/' not in url and 'imgur.com' in url:
                urls.append(url)

        # Gallery
        if hasattr(submission, 'is_gallery') and submission.is_gallery:
            if hasattr(submission, 'media_metadata'):
                for item in submission.media_metadata.values():
                    if 's' in item and 'u' in item['s']:
                        # Decode HTML entities in URL
                        image_url = item['s']['u'].replace('&amp;', '&')
                        urls.append(image_url)

        return urls

    def _extract_post_data(self, submission) -> Dict[str, Any]:
        """
        Extract post data from PRAW submission.

        Args:
            submission: PRAW submission object

        Returns:
            Dictionary with post data
        """
        image_urls = self._extract_image_urls(submission)

        # Extract flair information
        link_flair_text = getattr(submission, 'link_flair_text', None)
        link_flair_css_class = getattr(submission, 'link_flair_css_class', None)

        # Extract author flair (if author exists)
        author_flair_text = None
        if submission.author:
            author_flair_text = getattr(submission.author, 'flair_text', None) or \
                              getattr(submission, 'author_flair_text', None)

        return {
            'id': submission.id,
            'subreddit': submission.subreddit.display_name,
            'title': submission.title,
            'selftext': submission.selftext,
            'author': str(submission.author) if submission.author else '[deleted]',
            'score': submission.score,
            'num_comments': submission.num_comments,
            'created_utc': int(submission.created_utc),
            'permalink': submission.permalink,
            'url': submission.url,
            'is_nsfw': submission.over_18,
            'has_images': len(image_urls) > 0,
            'image_urls': image_urls,
            'link_flair_text': link_flair_text,
            'link_flair_css_class': link_flair_css_class,
            'author_flair_text': author_flair_text
        }

    def _collect_comments(self, submission) -> int:
        """
        Collect all comments from a submission.

        Args:
            submission: PRAW submission object

        Returns:
            Number of comments collected
        """
        try:
            comments = self.client.get_post_comments(submission)
            count = 0

            for comment in comments:
                # Skip non-comment objects (like MoreComments)
                if not isinstance(comment, praw.models.Comment):
                    continue

                # Skip deleted/removed comments
                if comment.body in ['[removed]', '[deleted]']:
                    continue

                comment_data = self._extract_comment_data(comment, submission.id)
                if self.db.insert_comment(comment_data):
                    count += 1

            logger.debug(f"Collected {count} comments for post {submission.id}")
            return count

        except Exception as e:
            logger.error(f"Error collecting comments for post {submission.id}: {e}")
            return 0

    def _extract_comment_data(self, comment, post_id: str) -> Dict[str, Any]:
        """
        Extract comment data from PRAW comment.

        Args:
            comment: PRAW comment object
            post_id: ID of the parent post

        Returns:
            Dictionary with comment data
        """
        # Determine parent ID and depth
        parent_id = None
        depth = 0

        if hasattr(comment, 'parent_id'):
            parent_id = comment.parent_id
            # If parent is the submission, this is a top-level comment (depth=0)
            if not parent_id.startswith('t1_'):  # t1_ = comment, t3_ = submission
                depth = 0
            else:
                # For nested comments, calculate depth
                depth = self._calculate_comment_depth(comment)

        return {
            'id': comment.id,
            'post_id': post_id,
            'parent_id': parent_id,
            'author': str(comment.author) if comment.author else '[deleted]',
            'body': comment.body,
            'score': comment.score,
            'created_utc': int(comment.created_utc),
            'permalink': comment.permalink,
            'depth': depth,
            'author_flair_text': comment.author_flair_text if hasattr(comment, 'author_flair_text') else None,
        }

    def _calculate_comment_depth(self, comment) -> int:
        """
        Calculate the depth of a comment in the comment tree.

        Args:
            comment: PRAW comment object

        Returns:
            Depth (0 = top-level)
        """
        depth = 0
        current = comment
        max_depth = 10  # Prevent infinite loops

        while hasattr(current, 'parent_id') and depth < max_depth:
            parent_id = current.parent_id
            # If parent is a submission (t3_), we're at top level
            if not parent_id.startswith('t1_'):
                break
            depth += 1
            # Try to get parent comment
            try:
                current = current.parent()
            except:
                break

        return depth
