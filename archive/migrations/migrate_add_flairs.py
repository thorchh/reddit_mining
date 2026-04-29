#!/usr/bin/env python3
"""
Database migration: Add flair columns to posts table
"""

import sqlite3
from config.settings import settings

def migrate():
    """Add flair columns to existing posts table."""
    conn = sqlite3.connect(settings.DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()

    print("Adding flair columns to posts table...")

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(posts)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'link_flair_text' not in columns:
        cursor.execute("ALTER TABLE posts ADD COLUMN link_flair_text TEXT")
        print("✓ Added link_flair_text column")
    else:
        print("  link_flair_text already exists")

    if 'link_flair_css_class' not in columns:
        cursor.execute("ALTER TABLE posts ADD COLUMN link_flair_css_class TEXT")
        print("✓ Added link_flair_css_class column")
    else:
        print("  link_flair_css_class already exists")

    if 'author_flair_text' not in columns:
        cursor.execute("ALTER TABLE posts ADD COLUMN author_flair_text TEXT")
        print("✓ Added author_flair_text column")
    else:
        print("  author_flair_text already exists")

    # Add index
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_link_flair ON posts(link_flair_text)")
    print("✓ Added flair index")

    conn.commit()
    conn.close()

    print("\n✅ Migration complete!")

if __name__ == '__main__':
    migrate()
