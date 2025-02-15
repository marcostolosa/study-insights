import os
import praw
import openai
import yaml
import time
import logging
import sqlite3
from datetime import datetime, timezone
from html import escape
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from dotenv import load_dotenv
load_dotenv()  # Carrega variáveis do arquivo .env

# Configuração inicial de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('oscp_analysis.log'),
        logging.StreamHandler()
    ]
)

class OSCPAnalyzer:
    def __init__(self):
        self.config = self.load_config()
        self.metrics = DataMetrics()
        self.conn = self.setup_database()
        self.reddit = self.initialize_reddit()
        
    @staticmethod
    def load_config():
        with open('config.yaml') as f:
            return yaml.safe_load(f)
    
    def setup_database(self):
        conn = sqlite3.connect(self.config['database']['file'])
        conn.execute("PRAGMA journal_mode=WAL")
        
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    selftext TEXT,
                    url TEXT,
                    created_utc REAL,
                    score INTEGER,          
                    num_comments INTEGER    
                )''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    id TEXT PRIMARY KEY,
                    post_id TEXT,
                    comment_body TEXT,
                    created_utc REAL,
                    score INTEGER,
                    FOREIGN KEY (post_id) REFERENCES posts(id)
                )''')
            
            conn.execute('CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments (post_id)')
        
        return conn
    
    def initialize_reddit(self):
        return praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT")
        )
    
    @staticmethod
    def handle_api_errors(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except praw.exceptions.APIException as e:
                logging.error(f"API Error: {e}")
                time.sleep(60)
                return wrapper(*args, **kwargs)
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                raise
        return wrapper
    
    def is_useful_post(self, post):
        content = f"{post.title} {post.selftext}".lower()
        return any(
            keyword in content
            for category in self.config['keywords'].values()
            for keyword in category
        ) and len(post.selftext) > self.config['post_min_length']
    
    @handle_api_errors
    def collect_posts(self):
        subreddit = self.reddit.subreddit(self.config['subreddit'])
        posts = []
        after = None
        
        for _ in range(self.config['max_pagination']):
            results = list(subreddit.search(
                self.config['search_query'],
                sort=self.config['sort'],
                time_filter=self.config['time_filter'],
                limit=self.config['batch_size'],
                params={'after': after}
            ))
            
            if not results:
                break
                
            posts.extend([post for post in results if self.is_useful_post(post)])
            after = results[-1].fullname
        
        self.metrics.posts_processed = len(posts)
        return posts
    
    def process_comments(self, post):
        try:
            post.comments.replace_more(limit=None)
            return [
                (str(comment.id), comment.body, comment.created_utc, comment.score)
                for comment in post.comments.list()
            ]
        except Exception as e:
            logging.error(f"Error processing comments: {e}")
            return []
    
    def save_data(self, posts):
        with ThreadPoolExecutor(max_workers=4) as executor, self.conn:
            for post in posts:
                try:
                    self.conn.execute('''
                        INSERT OR IGNORE INTO posts 
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        post.id,
                        escape(post.title),
                        escape(post.selftext),
                        post.url,
                        post.created_utc,
                        post.score,
                        post.num_comments
                    ))
                    
                    comments = self.process_comments(post)
                    self.metrics.comments_analyzed += len(comments)
                    
                    executor.submit(
                        self.conn.executemany,
                        '''INSERT OR IGNORE INTO comments 
                        VALUES (?, ?, ?, ?, ?)''',
                        [(c[0], post.id, escape(c[1]), c[2], c[3]) for c in comments]
                    )
                    
                except Exception as e:
                    logging.error(f"Error saving post {post.id}: {e}")
    
    def analyze_content(self, text):
        try:
            return openai.chat.completions.create(
                model=self.config['openai']['model'],
                messages=[{
                    "role": "system",
                    "content": self.config['openai']['system_prompt']
                }, {
                    "role": "user",
                    "content": text[:self.config['openai']['max_tokens']]
                }],
                temperature=self.config['openai']['temperature']
            ).choices[0].message.content
        except Exception as e:
            logging.error(f"OpenAI API Error: {e}")
            return None
    
    def generate_report(self):
        with self.conn:
            cur = self.conn.execute('''
                SELECT p.title, p.selftext, c.comment_body 
                FROM posts p
                LEFT JOIN comments c ON p.id = c.post_id
            ''')
            
            combined_text = "\n".join(
                f"Post: {row[0]}\n{row[1]}\nComment: {row[2]}\n"
                for row in cur.fetchall()
            )
        
        analysis = self.analyze_content(combined_text)
        
        with open(self.config['output_file'], 'w') as f:
            f.write(analysis)
        
        return analysis

class DataMetrics:
    def __init__(self):
        self.posts_processed = 0
        self.comments_analyzed = 0

if __name__ == '__main__':
    analyzer = OSCPAnalyzer()
    
    try:
        logging.info("Starting data collection...")
        posts = analyzer.collect_posts()
        
        logging.info(f"Collected {len(posts)} posts. Saving to database...")
        analyzer.save_data(posts)
        
        logging.info("Generating analysis report...")
        report = analyzer.generate_report()
        
        logging.info(f"Analysis complete. Results saved to {analyzer.config['output_file']}")
        logging.info(f"Metrics: Posts={analyzer.metrics.posts_processed} Comments={analyzer.metrics.comments_analyzed}")
        
    except Exception as e:
        logging.error(f"Critical error: {e}")
        raise