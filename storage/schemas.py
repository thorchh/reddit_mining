"""
SQL schemas for Reddit mining database.
"""

CREATE_POSTS_TABLE = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    subreddit TEXT NOT NULL,
    title TEXT NOT NULL,
    selftext TEXT,
    author TEXT,
    score INTEGER,
    num_comments INTEGER,
    created_utc INTEGER,
    permalink TEXT,
    url TEXT,
    is_nsfw BOOLEAN,
    collected_at INTEGER,
    has_images BOOLEAN,
    image_urls TEXT,
    link_flair_text TEXT,
    link_flair_css_class TEXT,
    author_flair_text TEXT
);
"""

CREATE_COMMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL,
    parent_id TEXT,
    author TEXT,
    body TEXT NOT NULL,
    score INTEGER,
    created_utc INTEGER,
    permalink TEXT,
    depth INTEGER,
    collected_at INTEGER,
    author_flair_text TEXT,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);
"""

CREATE_CONSENSUS_TABLE = """
CREATE TABLE IF NOT EXISTS consensus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL,
    consensus_answer TEXT,
    confidence_score REAL,
    top_answers TEXT,
    num_agreeing_comments INTEGER,
    methodology TEXT,
    extracted_at INTEGER,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);
"""

CREATE_COLLECTION_METADATA_TABLE = """
CREATE TABLE IF NOT EXISTS collection_metadata (
    subreddit TEXT PRIMARY KEY,
    last_collected_post_id TEXT,
    last_collection_time INTEGER,
    total_posts_collected INTEGER
);
"""

# Indexes for better query performance
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_posts_subreddit ON posts(subreddit);",
    "CREATE INDEX IF NOT EXISTS idx_posts_has_images ON posts(has_images);",
    "CREATE INDEX IF NOT EXISTS idx_posts_link_flair ON posts(link_flair_text);",
    "CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id);",
    "CREATE INDEX IF NOT EXISTS idx_comments_depth ON comments(depth);",
    "CREATE INDEX IF NOT EXISTS idx_consensus_post_id ON consensus(post_id);",
]

ALL_TABLES = [
    CREATE_POSTS_TABLE,
    CREATE_COMMENTS_TABLE,
    CREATE_CONSENSUS_TABLE,
    CREATE_COLLECTION_METADATA_TABLE
]
