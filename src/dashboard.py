import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
from typing import Tuple


# Configuração de logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)


def validate_database(db_path: Path) -> bool:
    """Valida se o arquivo do banco de dados existe."""
    if not db_path.exists():
        st.error(f"Arquivo do banco de dados não encontrado: {db_path}")
        logging.error(f"Arquivo do banco de dados não encontrado: {db_path}")
        return False
    return True


def load_data(db_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Carrega posts e comentários do banco de dados SQLite."""
    try:
        if not validate_database(db_path):
            return pd.DataFrame(), pd.DataFrame()

        with sqlite3.connect(db_path) as conn:
            # Carregar posts
            posts = pd.read_sql('SELECT * FROM posts', conn)
            # Carregar comentários
            comments = pd.read_sql('SELECT * FROM comments', conn)

        # Formatar timestamps para leitura humana
        if not posts.empty:
            posts['created_utc'] = pd.to_datetime(posts['created_utc'], unit='s').dt.strftime('%Y-%m-%d %H:%M:%S')
        if not comments.empty:
            comments['created_utc'] = pd.to_datetime(comments['created_utc'], unit='s').dt.strftime('%Y-%m-%d %H:%M:%S')

        return posts, comments

    except sqlite3.Error as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        logging.error(f"Erro ao conectar ao banco de dados: {e}")
        return pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        st.error(f"Erro inesperado: {e}")
        logging.error(f"Erro inesperado: {e}")
        return pd.DataFrame(), pd.DataFrame()


def display_overview(posts: pd.DataFrame, comments: pd.DataFrame):
    """Exibe uma visão geral dos dados."""
    st.header("Visão Geral")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Posts", len(posts))
    with col2:
        st.metric("Total de Comentários", len(comments))
    with col3:
        avg_score = posts['score'].mean() if not posts.empty else 0
        st.metric("Pontuação Média dos Posts", round(avg_score, 2))


def display_recent_posts(posts: pd.DataFrame):
    """Exibe uma tabela com os posts mais recentes."""
    st.header("Posts Recentes")
    if posts.empty:
        st.warning("Nenhum post disponível.")
        return

    # Exibir apenas colunas relevantes
    for i, row in posts[['title', 'selftext', 'score', 'num_comments', 'created_utc']].head(10).iterrows():
        with st.expander(f"Post {i+1}: {row['title']}"):
            st.write("**Pontuação:**", row['score'])
            st.write("**Comentários:**", row['num_comments'])
            st.write("**Criado em:**", row['created_utc'])
            st.markdown("**Conteúdo:**")
            st.markdown(row['selftext'])  # Renderiza o conteúdo em Markdown


def display_ai_analysis(report_path: Path):
    """Exibe o relatório de análise gerado pela IA."""
    st.header("Relatório de Análise")
    if not report_path.exists():
        st.warning("Relatório de análise ainda não foi gerado.")
        return

    try:
        # Ler o relatório com codificação UTF-8
        with open(report_path, 'r', encoding='utf-8') as f:
            report = f.read()
        st.markdown(report)
    except Exception as e:
        st.error(f"Erro ao carregar o relatório: {e}")


def main():
    """Função principal para executar o dashboard."""
    st.set_page_config(page_title="OSCP Insights Dashboard", layout="wide")
    st.title("OSCP Insights Dashboard")

    # Definir caminhos para o banco de dados e relatório
    db_path = Path("../data/oscp_posts.db").resolve()
    report_path = Path("../reports/oscp_analysis.txt").resolve()

    # Carregar dados
    posts, comments = load_data(db_path)

    if posts.empty or comments.empty:
        st.warning("Nenhum dado disponível para exibir.")
        return

    # Barra lateral para navegação
    st.sidebar.title("Navegação")
    page = st.sidebar.radio("Ir para", ["Visão Geral", "Posts Recentes", "Relatório de Análise"])

    # Exibir conteúdo com base na página selecionada
    if page == "Visão Geral":
        display_overview(posts, comments)
    elif page == "Posts Recentes":
        display_recent_posts(posts)
    elif page == "Relatório de Análise":
        display_ai_analysis(report_path)


if __name__ == '__main__':
    main()