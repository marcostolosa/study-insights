import os
import praw
import openai
from openai import OpenAI
import yaml
import time
import logging
import sqlite3
from datetime import datetime
from html import escape
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from dotenv import load_dotenv
from typing import List, Tuple, Optional, Dict, Any
from threading import Lock
from pathlib import Path


# Carregar variáveis de ambiente
load_dotenv()

# Configuração de logging aprimorada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s - %(message)s',
    handlers=[
        logging.FileHandler('../logs/oscp_analysis.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class DatabaseManager:
    """Gerenciador seguro de conexões de banco de dados."""
    def __init__(self, db_file: str):
        self.db_file = db_file

    def __enter__(self) -> sqlite3.Connection:
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False, timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            logging.error(f"Erro no banco de dados: {exc_val}")
        self.conn.close()


class DataMetrics:
    """Métricas com controle thread-safe."""
    def __init__(self):
        self._lock = Lock()
        self.posts_processed = 0
        self.comments_analyzed = 0

    def increment_posts(self, count: int = 1) -> None:
        with self._lock:
            self.posts_processed += count

    def increment_comments(self, count: int = 1) -> None:
        with self._lock:
            self.comments_analyzed += count


class OSCPAnalyzer:
    def __init__(self):
        self.config = self.load_config()
        self.metrics = DataMetrics()
        self.reddit = self.initialize_reddit()
        self.setup_database()
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @staticmethod
    def load_config() -> Dict:
        """Carregar e validar a configuração do YAML."""
        try:
            with open('../config/config.yaml', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            required_keys = {'subreddit', 'database', 'openai', 'keywords'}
            if not required_keys.issubset(config.keys()):
                raise ValueError("Configuração incompleta no arquivo YAML.")

            return config
        except Exception as e:
            logging.critical(f"Erro ao carregar a configuração: {e}")
            raise

    def setup_database(self) -> None:
        """Inicializar o esquema do banco de dados."""
        with DatabaseManager(self.config['database']['file']) as conn:
            with conn:
                conn.execute('''CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    selftext TEXT,
                    url TEXT,
                    created_utc REAL,
                    score INTEGER,
                    num_comments INTEGER
                )''')
                conn.execute('''CREATE TABLE IF NOT EXISTS comments (
                    id TEXT PRIMARY KEY,
                    post_id TEXT,
                    comment_body TEXT,
                    created_utc REAL,
                    score INTEGER,
                    FOREIGN KEY (post_id) REFERENCES posts(id)
                )''')
                conn.execute('''CREATE INDEX IF NOT EXISTS idx_comments_post_id 
                ON comments (post_id)''')

    def initialize_reddit(self) -> praw.Reddit:
        """Inicializar o cliente da API do Reddit."""
        return praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT"),
            ratelimit_seconds=300
        )

    @staticmethod
    def handle_api_errors(func):
        """Decorador para lidar com erros de API com backoff exponencial."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except praw.exceptions.APIException as e:
                    logging.error(f"Erro na API (Tentativa {attempt+1}/{max_retries}): {e}")
                    time.sleep(2 ** attempt)
                except Exception as e:
                    logging.error(f"Erro inesperado: {e}")
                    raise
            raise Exception(f"Falha após {max_retries} tentativas.")
        return wrapper

    def is_useful_post(self, post: praw.models.Submission) -> bool:
        """Determinar se um post é relevante com base em palavras-chave e comprimento."""
        content = f"{post.title} {post.selftext}".lower()
        min_length = self.config.get('post_min_length', 100)
        technical_terms = self.config['keywords'].get('technical_terms', [])
        return (
            any(keyword in content for keyword in technical_terms)
            and len(post.selftext) > min_length
        )

    @handle_api_errors
    def collect_posts(self) -> List[praw.models.Submission]:
        """Coletar posts relevantes do Reddit."""
        subreddit = self.reddit.subreddit(self.config['subreddit'])
        posts = []
        after = None

        for _ in range(self.config.get('max_pagination', 5)):
            results = list(subreddit.search(
                self.config['search_query'],
                sort=self.config['sort'],
                time_filter=self.config['time_filter'],
                limit=self.config['batch_size'],
                params={'after': after}
            ))

            if not results:
                break

            useful_posts = [post for post in results if self.is_useful_post(post)]
            if not useful_posts:
                break

            posts.extend(useful_posts)
            after = results[-1].fullname

        self.metrics.increment_posts(len(posts))
        return posts

    def process_comments(self, post: praw.models.Submission) -> List[Tuple[str, str, float, int]]:
        """Extrair e filtrar comentários de um post."""
        try:
            post.comments.replace_more(limit=10)
            return [
                (str(comment.id), comment.body, comment.created_utc, comment.score)
                for comment in post.comments.list()
                if len(comment.body) >= self.config.get('comment_min_length', 20)
            ]
        except Exception as e:
            logging.error(f"Erro ao processar comentários: {e}")
            return []

    def save_data(self, posts: List[praw.models.Submission]) -> None:
        """Salvar posts e comentários no banco de dados."""
        with ThreadPoolExecutor(max_workers=4) as executor:
            for post in posts:
                try:
                    with DatabaseManager(self.config['database']['file']) as conn:
                        with conn:
                            conn.execute('''INSERT OR IGNORE INTO posts 
                            VALUES (?, ?, ?, ?, ?, ?, ?)''', (
                                post.id,
                                post.title,
                                post.selftext,
                                post.url,
                                post.created_utc,
                                post.score,
                                post.num_comments
                            ))

                    comments = self.process_comments(post)
                    self.metrics.increment_comments(len(comments))
                    executor.submit(self.save_comments, comments, post.id)

                except Exception as e:
                    logging.error(f"Erro ao salvar o post {post.id}: {e}")

    def save_comments(self, comments: List[Tuple[str, str, float, int]], post_id: str) -> None:
        """Salvar comentários no banco de dados."""
        try:
            with DatabaseManager(self.config['database']['file']) as conn:
                with conn:
                    conn.executemany(
                        '''INSERT OR IGNORE INTO comments 
                        VALUES (?, ?, ?, ?, ?)''',
                        [(c[0], post_id, c[1], c[2], c[3]) for c in comments]
                    )
        except Exception as e:
            logging.error(f"Erro ao salvar comentários para o post {post_id}: {e}")

    def analyze_content(self, text: str) -> Optional[str]:
        """Analisar conteúdo usando a API do OpenAI."""
        try:
            response = self.openai_client.chat.completions.create(
                model=self.config['openai']['model'],
                messages=[{
                    "role": "system",
                    "content": self.config['openai']['system_prompt']
                }, {
                    "role": "user",
                    "content": text[:self.config['openai']['max_input_tokens']]
                }],
                temperature=self.config['openai']['temperature'],
                max_tokens=self.config['openai'].get('max_response_tokens', 500)
            )
            return response.choices[0].message.content
        except openai.OpenAIError as e:
            logging.error(f"Erro na API do OpenAI: {e}")
            return None

    def generate_report(self) -> Optional[str]:
        """Gerar um relatório de análise a partir dos dados salvos."""
        try:
            combined_text = []
            with DatabaseManager(self.config['database']['file']) as conn:
                cur = conn.execute('''SELECT p.title, p.selftext, c.comment_body 
                FROM posts p
                LEFT JOIN comments c ON p.id = c.post_id''')
                for row in cur.fetchall():
                    combined_text.append(f"Post: {row[0]}\n{row[1]}\nComentário: {row[2]}\n")

            analysis = []
            CHUNK_SIZE = 3000  # Tokens aproximados
            for i in range(0, len(combined_text), CHUNK_SIZE):
                chunk = " ".join(combined_text[i:i+CHUNK_SIZE])
                result = self.analyze_content(chunk)
                if result:
                    analysis.append(result)

            report_content = "\n".join(analysis)

            report_dir = '../reports'
            os.makedirs(report_dir, exist_ok=True)

            # Salvar o relatório com codificação UTF-8
            with open(f'{report_dir}/oscp_analysis.txt', 'w', encoding='utf-8') as f:
                f.write(report_content)

            return report_content

        except Exception as e:
            logging.error(f"Erro ao gerar o relatório: {e}")
            return None


if __name__ == '__main__':
    analyzer = OSCPAnalyzer()

    try:
        logging.info("Iniciando coleta de dados...")
        posts = analyzer.collect_posts()

        logging.info(f"Coletados {len(posts)} posts. Salvando no banco de dados...")
        analyzer.save_data(posts)

        logging.info("Gerando relatório de análise...")
        report = analyzer.generate_report()

        logging.info(f"Análise concluída. Resultados salvos em ../reports/oscp_analysis.txt")
        logging.info(f"Métricas: Posts={analyzer.metrics.posts_processed} Comentários={analyzer.metrics.comments_analyzed}")

    except Exception as e:
        logging.critical(f"Erro crítico: {e}")
        raise