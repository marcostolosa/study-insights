import streamlit as st
import sqlite3
import pandas as pd
from typing import Tuple

def load_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    conn = sqlite3.connect('data/oscp_posts.db')
    posts = pd.read_sql('SELECT * FROM posts', conn)
    comments = pd.read_sql('SELECT * FROM comments', conn)
    conn.close()
    return posts, comments

def main():
    st.title('OSCP Insights Dashboard')
    
    posts, comments = load_data()
    
    # Metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Posts", len(posts))
    with col2:
        st.metric("Total Comments", len(comments))
    
    # Recent Posts
    st.subheader("Recent Posts")
    st.dataframe(posts[['title', 'score', 'num_comments', 'created_utc']].head(10))
    
    # Analysis Report
    st.subheader("AI Analysis Report")
    try:
        with open('reports/oscp_analysis.txt', 'r') as f:
            report = f.read()
        st.markdown(report)
    except FileNotFoundError:
        st.warning("Analysis report not found yet")
    except Exception as e:
        st.error(f"An error occurred while loading the report: {e}")

if __name__ == '__main__':
    main()