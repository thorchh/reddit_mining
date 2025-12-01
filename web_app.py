#!/usr/bin/env python3
"""
Streamlit Web App for Reddit Mining Data Visualization

Visualize collected Reddit posts, comments, and consensus answers.
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime
from storage.database import Database

# Page configuration
st.set_page_config(
    page_title="Reddit Mining Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .post-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 0.5rem;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .confidence-high {
        color: #28a745;
        font-weight: bold;
    }
    .confidence-medium {
        color: #ffc107;
        font-weight: bold;
    }
    .confidence-low {
        color: #dc3545;
        font-weight: bold;
    }
    .comment-box {
        background-color: #f8f9fa;
        border-left: 3px solid #007bff;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
    }
    .flair-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 0.5rem;
    }
    .flair-solved {
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    .flair-likely {
        background-color: #fff3cd;
        color: #856404;
        border: 1px solid #ffeaa7;
    }
    .flair-unsolved {
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
    }
    .flair-default {
        background-color: #e7f3ff;
        color: #004085;
        border: 1px solid #b8daff;
    }
    .author-flair {
        background-color: #f3e5f5;
        color: #4a148c;
        border: 1px solid #e1bee7;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database connection
@st.cache_resource
def get_database():
    """Get database connection (cached)."""
    return Database()

db = get_database()

# Sidebar navigation
st.sidebar.title("📊 Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Dashboard", "Browse Posts", "Consensus Analysis", "Dataset Export"]
)

# Sidebar filters
st.sidebar.title("🔍 Filters")
stats = db.get_statistics()
subreddits = ["All"] + list(stats.get('posts_by_subreddit', {}).keys())
selected_subreddit = st.sidebar.selectbox("Subreddit", subreddits)

min_confidence = st.sidebar.slider(
    "Minimum Confidence",
    min_value=0.0,
    max_value=1.0,
    value=0.0,
    step=0.1
)

show_nsfw = st.sidebar.checkbox("Include NSFW posts", value=False)

# Get unique flairs for filter
cursor = db.conn.cursor()
cursor.execute("SELECT DISTINCT link_flair_text FROM posts WHERE link_flair_text IS NOT NULL ORDER BY link_flair_text")
unique_flairs = [row[0] for row in cursor.fetchall()]
selected_flair = st.sidebar.selectbox("Post Flair", ["All"] + unique_flairs) if unique_flairs else "All"

# Helper functions
def get_flair_class(flair_text):
    """Get CSS class for flair badge based on text."""
    if not flair_text:
        return "flair-default"
    flair_lower = flair_text.lower()
    if "solved" in flair_lower and "likely" not in flair_lower:
        return "flair-solved"
    elif "likely" in flair_lower:
        return "flair-likely"
    elif "unsolved" in flair_lower or "open" in flair_lower:
        return "flair-unsolved"
    else:
        return "flair-default"

# Helper functions
def get_confidence_class(confidence):
    """Get CSS class for confidence score."""
    if confidence >= 0.7:
        return "confidence-high"
    elif confidence >= 0.4:
        return "confidence-medium"
    else:
        return "confidence-low"

def get_confidence_label(confidence):
    """Get label for confidence score."""
    if confidence >= 0.7:
        return "High"
    elif confidence >= 0.4:
        return "Medium"
    else:
        return "Low"

def format_timestamp(timestamp):
    """Format Unix timestamp to readable date."""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")

# PAGE: Dashboard
if page == "Dashboard":
    st.markdown('<div class="main-header">📊 Reddit Mining Dashboard</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Statistics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Posts", stats.get('total_posts', 0))
    with col2:
        st.metric("Posts with Images", stats.get('posts_with_images', 0))
    with col3:
        st.metric("Total Comments", stats.get('total_comments', 0))
    with col4:
        st.metric("Consensus Extracted", stats.get('consensus_extracted', 0))

    st.markdown("---")

    # Posts by subreddit
    st.subheader("📈 Posts by Subreddit")
    posts_by_sub = stats.get('posts_by_subreddit', {})
    if posts_by_sub:
        df_subs = pd.DataFrame([
            {"Subreddit": f"r/{sub}", "Posts": count}
            for sub, count in posts_by_sub.items()
        ]).sort_values("Posts", ascending=False)

        st.bar_chart(df_subs.set_index("Subreddit"))
        st.dataframe(df_subs, use_container_width=True)
    else:
        st.info("No data collected yet. Run the collection script first!")

    st.markdown("---")

    # Recent posts
    st.subheader("🆕 Recent Posts")
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT id, subreddit, title, score, num_comments, has_images, collected_at
        FROM posts
        ORDER BY collected_at DESC
        LIMIT 10
    """)
    recent_posts = cursor.fetchall()

    if recent_posts:
        recent_df = pd.DataFrame([
            {
                "Subreddit": f"r/{row[1]}",
                "Title": row[2][:60] + "..." if len(row[2]) > 60 else row[2],
                "Score": row[3],
                "Comments": row[4],
                "Has Images": "✓" if row[5] else "✗",
                "Collected": format_timestamp(row[6])
            }
            for row in recent_posts
        ])
        st.dataframe(recent_df, use_container_width=True)
    else:
        st.info("No posts collected yet.")

# PAGE: Browse Posts
elif page == "Browse Posts":
    st.markdown('<div class="main-header">🔍 Browse Posts</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Build query
    query = """
        SELECT p.id, p.subreddit, p.title, p.selftext, p.image_urls, p.score,
               p.num_comments, p.is_nsfw, p.created_utc, p.permalink,
               c.consensus_answer, c.confidence_score, c.top_answers,
               p.link_flair_text, p.link_flair_css_class, p.author_flair_text, p.author
        FROM posts p
        LEFT JOIN consensus c ON p.id = c.post_id
        WHERE p.has_images = 1
    """
    params = []

    if selected_subreddit != "All":
        query += " AND p.subreddit = ?"
        params.append(selected_subreddit)

    if not show_nsfw:
        query += " AND p.is_nsfw = 0"

    if min_confidence > 0:
        query += " AND c.confidence_score >= ?"
        params.append(min_confidence)

    if selected_flair != "All":
        query += " AND p.link_flair_text = ?"
        params.append(selected_flair)

    query += " ORDER BY p.collected_at DESC LIMIT 20"

    cursor = db.conn.cursor()
    cursor.execute(query, params)
    posts = cursor.fetchall()

    st.write(f"Found {len(posts)} posts")

    # Display posts
    for row in posts:
        with st.container():
            st.markdown('<div class="post-card">', unsafe_allow_html=True)

            # Header
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"### r/{row[1]}")
                st.markdown(f"**{row[2]}**")

                # Display flairs
                flair_html = ""
                if row[13]:  # link_flair_text
                    flair_class = get_flair_class(row[13])
                    flair_html += f'<span class="flair-badge {flair_class}">{row[13]}</span>'
                if row[15] and row[16]:  # author_flair_text and author
                    flair_html += f'<span class="flair-badge author-flair">u/{row[16]}: {row[15]}</span>'
                if flair_html:
                    st.markdown(flair_html, unsafe_allow_html=True)

            with col2:
                st.metric("Score", row[5])
            with col3:
                st.metric("Comments", row[6])

            # Post content
            if row[3]:  # selftext
                with st.expander("Show post text"):
                    st.write(row[3])

            # Images
            image_urls = json.loads(row[4]) if row[4] else []
            if image_urls:
                st.markdown("**Images:**")
                cols = st.columns(min(len(image_urls), 3))
                for i, url in enumerate(image_urls[:3]):
                    with cols[i]:
                        try:
                            st.image(url, use_container_width=True)
                        except:
                            st.markdown(f"[Image Link]({url})")

            # Consensus
            if row[10]:  # consensus_answer
                confidence = row[11]
                confidence_class = get_confidence_class(confidence)
                confidence_label = get_confidence_label(confidence)

                st.markdown("---")
                st.markdown("**Consensus Answer:**")
                st.markdown(f'<div class="comment-box">{row[10]}</div>', unsafe_allow_html=True)
                st.markdown(
                    f'Confidence: <span class="{confidence_class}">{confidence:.2f} ({confidence_label})</span>',
                    unsafe_allow_html=True
                )

                # Alternative answers
                if row[12]:  # top_answers
                    with st.expander("Show alternative answers"):
                        top_answers = json.loads(row[12])
                        for answer in top_answers[1:4]:  # Skip first (same as consensus)
                            st.markdown(f"**#{answer['rank']} (Score: {answer['score']})** by u/{answer['author']}")
                            st.markdown(f"> {answer['answer']}")
                            st.markdown("")
            else:
                st.info("No consensus extracted yet")

            # Footer
            st.markdown(f"[View on Reddit](https://reddit.com{row[9]})")

            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("---")

# PAGE: Consensus Analysis
elif page == "Consensus Analysis":
    st.markdown('<div class="main-header">📊 Consensus Analysis</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Get consensus data
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT p.subreddit, c.confidence_score, c.post_id, p.title
        FROM consensus c
        JOIN posts p ON c.post_id = p.id
    """)
    consensus_data = cursor.fetchall()

    if not consensus_data:
        st.warning("No consensus data available. Run extract_consensus.py first!")
    else:
        # Confidence distribution
        st.subheader("📈 Confidence Score Distribution")
        df_confidence = pd.DataFrame([
            {"Subreddit": row[0], "Confidence": row[1], "Post ID": row[2], "Title": row[3]}
            for row in consensus_data
        ])

        # Filter by subreddit
        if selected_subreddit != "All":
            df_confidence = df_confidence[df_confidence['Subreddit'] == selected_subreddit]

        # Histogram
        st.bar_chart(df_confidence['Confidence'].value_counts().sort_index())

        # Statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Mean Confidence", f"{df_confidence['Confidence'].mean():.2f}")
        with col2:
            st.metric("Median Confidence", f"{df_confidence['Confidence'].median():.2f}")
        with col3:
            high_conf = (df_confidence['Confidence'] >= 0.7).sum()
            st.metric("High Confidence", f"{high_conf} ({high_conf/len(df_confidence)*100:.1f}%)")
        with col4:
            low_conf = (df_confidence['Confidence'] < 0.4).sum()
            st.metric("Low Confidence", f"{low_conf} ({low_conf/len(df_confidence)*100:.1f}%)")

        st.markdown("---")

        # Confidence by subreddit
        st.subheader("📊 Average Confidence by Subreddit")
        conf_by_sub = df_confidence.groupby('Subreddit')['Confidence'].agg(['mean', 'count']).reset_index()
        conf_by_sub.columns = ['Subreddit', 'Avg Confidence', 'Posts']
        conf_by_sub = conf_by_sub.sort_values('Avg Confidence', ascending=False)

        st.dataframe(conf_by_sub, use_container_width=True)

        st.markdown("---")

        # Top/Bottom confidence posts
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("✅ Highest Confidence Posts")
            top_conf = df_confidence.nlargest(5, 'Confidence')
            for _, row in top_conf.iterrows():
                st.markdown(f"**{row['Confidence']:.2f}** - r/{row['Subreddit']}")
                st.markdown(f"_{row['Title'][:60]}..._")
                st.markdown("")

        with col2:
            st.subheader("⚠️ Lowest Confidence Posts")
            bottom_conf = df_confidence.nsmallest(5, 'Confidence')
            for _, row in bottom_conf.iterrows():
                st.markdown(f"**{row['Confidence']:.2f}** - r/{row['Subreddit']}")
                st.markdown(f"_{row['Title'][:60]}..._")
                st.markdown("")

# PAGE: Dataset Export
elif page == "Dataset Export":
    st.markdown('<div class="main-header">💾 Dataset Export</div>', unsafe_allow_html=True)
    st.markdown("---")

    st.subheader("Export Settings")

    col1, col2 = st.columns(2)
    with col1:
        export_min_confidence = st.slider(
            "Minimum Confidence for Export",
            min_value=0.0,
            max_value=1.0,
            value=0.4,
            step=0.05
        )
    with col2:
        export_filename = st.text_input("Export Filename", value="dataset.jsonl")

    # Preview count
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM posts p
        JOIN consensus c ON p.id = c.post_id
        WHERE c.confidence_score >= ?
    """, (export_min_confidence,))
    export_count = cursor.fetchone()[0]

    st.info(f"📊 {export_count} posts will be exported with confidence >= {export_min_confidence}")

    if st.button("Export Dataset", type="primary"):
        from processors.consensus_extractor import ConsensusExtractor

        with st.spinner("Exporting dataset..."):
            extractor = ConsensusExtractor(db)
            extractor.export_dataset(
                output_path=export_filename,
                min_confidence=export_min_confidence
            )

        st.success(f"✅ Dataset exported to {export_filename}")

        # Show sample
        st.subheader("Sample Entry")
        with open(export_filename, 'r') as f:
            first_line = f.readline()
            sample = json.loads(first_line)
            st.json(sample)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### About")
st.sidebar.info(
    "Reddit Mining Dashboard for VLM Sycophancy Research\n\n"
    "Built with Streamlit"
)
