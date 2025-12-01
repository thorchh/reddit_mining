import praw
import time
from functools import wraps
from typing import Optional
import logging

from config.settings import settings

logger = logging.getLogger('reddit_mining.client')

class RateLimiter:
    """Rate limiter to respect Reddit API limits (60 requests/minute)."""

    def __init__(self, max_requests: int = 60, period: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum number of requests allowed
            period: Time period in seconds
        """
        self.max_requests = max_requests
        self.period = period
        self.requests = []

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        now = time.time()
        # Remove requests older than the period
        self.requests = [req_time for req_time in self.requests if now - req_time < self.period]

        if len(self.requests) >= self.max_requests:
            # Calculate wait time
            oldest_request = min(self.requests)
            wait_time = self.period - (now - oldest_request) + 1
            if wait_time > 0:
                logger.info(f"Rate limit reached. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                # Clear old requests after waiting
                now = time.time()
                self.requests = [req_time for req_time in self.requests if now - req_time < self.period]

        # Record this request
        self.requests.append(time.time())


def retry_on_error(max_retries: int = 3, backoff: float = 2.0):
    """
    Decorator to retry function on error with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        backoff: Backoff multiplier for wait time
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed after {max_retries} attempts: {e}")
                        raise
                    wait_time = backoff ** attempt
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        return wrapper
    return decorator


class RedditClient:
    """
    Wrapper around PRAW with rate limiting and error handling.
    """

    def __init__(self):
        """Initialize Reddit client with credentials from settings."""
        settings.validate()

        self.rate_limiter = RateLimiter(
            max_requests=settings.RATE_LIMIT_REQUESTS,
            period=settings.RATE_LIMIT_PERIOD
        )

        logger.info("Initializing Reddit client...")
        self.reddit = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=settings.REDDIT_USER_AGENT,
            username=settings.REDDIT_USERNAME,
            password=settings.REDDIT_PASSWORD
        )

        # Test connection
        try:
            username = self.reddit.user.me().name
            logger.info(f"Successfully authenticated as u/{username}")
        except Exception as e:
            logger.error(f"Failed to authenticate: {e}")
            raise

    @retry_on_error(max_retries=3, backoff=2.0)
    def get_subreddit(self, subreddit_name: str):
        """
        Get a subreddit instance with rate limiting.

        Args:
            subreddit_name: Name of the subreddit (without 'r/')

        Returns:
            praw.models.Subreddit instance
        """
        self.rate_limiter.wait_if_needed()
        logger.debug(f"Accessing subreddit r/{subreddit_name}")
        return self.reddit.subreddit(subreddit_name)

    @retry_on_error(max_retries=3, backoff=2.0)
    def get_top_posts(self, subreddit_name: str, time_filter: str = 'year', limit: int = 100):
        """
        Get top posts from a subreddit.

        Args:
            subreddit_name: Name of the subreddit
            time_filter: Time filter ('hour', 'day', 'week', 'month', 'year', 'all')
            limit: Maximum number of posts to retrieve

        Returns:
            Generator of praw.models.Submission objects
        """
        self.rate_limiter.wait_if_needed()
        subreddit = self.get_subreddit(subreddit_name)
        logger.info(f"Fetching top {limit} posts from r/{subreddit_name} (time_filter={time_filter})")
        return subreddit.top(time_filter=time_filter, limit=limit)

    @retry_on_error(max_retries=3, backoff=2.0)
    def get_post_comments(self, submission, limit: Optional[int] = None):
        """
        Get all comments from a submission.

        Args:
            submission: praw.models.Submission object
            limit: Maximum depth to expand "more comments" (None = all)

        Returns:
            List of comments
        """
        self.rate_limiter.wait_if_needed()
        logger.debug(f"Fetching comments for post {submission.id}")

        # Replace "more comments" with actual comments
        # limit=0 means skip "load more comments" links entirely for speed
        submission.comments.replace_more(limit=0)

        return submission.comments.list()

    def test_connection(self) -> bool:
        """
        Test Reddit API connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            user = self.reddit.user.me()
            logger.info(f"Connection test successful. Logged in as u/{user.name}")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
