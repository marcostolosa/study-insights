# OSCP Insights: Analisador de Sucesso no OSCP com Reddit e IA 🚀🔒

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Docker Pronto](https://img.shields.io/badge/docker-%E2%9C%94-green)](https://www.docker.com/)

Uma ferramenta avançada que transforma discussões da comunidade OSCP do Reddit em insights acionáveis usando análise de IA e visualização interativa.

**Demonstração:** [Preview do Dashboard](#dashboard-preview)

## 📌 Sumário
- [Funcionalidades](#-funcionalidades)
- [Tecnologias](#-tecnologias)
- [Começando](#-começando)
  - [Pré-requisitos](#pré-requisitos)
  - [Instalação](#instalação)
- [Configuração](#-configuração)
- [Uso](#-uso)
- [Dashboard](#-dashboard)
- [Docker](#-docker)
- [Solução de Problemas](#-solução-de-problemas)
- [Contribuição](#-contribuição)
- [Licença](#-licença)
- [Reconhecimentos](#-reconhecimentos)

## 🚀 Funcionalidades
- **Coleta Automatizada de Dados**
  - 📅 Filtro temporal (dados de 2023-2024)
  - 🎯 Filtragem inteligente de posts (análise com 700+ caracteres)
- **Geração de Insights com IA**
  - 🤖 Análise estratégica com GPT-4o
  - 🔍 Mapeamento MITRE ATT&CK
- **Gestão de Dados Profissional**
  - 🗄️ SQLite3 com transações WAL
  - 🔐 Sanitização de HTML e validação
- **Visualização de Dados**
  - 📈 Dashboard em tempo real
  - 🔄 Relatórios automáticos
- **Arquitetura Moderna**
  - 🐳 Pronto para Docker/Kubernetes
  - 🔄 Compatível com CI/CD


## 🛠️ Tecnologias
**Núcleo**  
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python)
![PRAW](https://img.shields.io/badge/PRAW-7.8%2B-FF4500?logo=reddit)
![OpenAI](https://img.shields.io/badge/OpenAI-1.0%2B-412991)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B)

**Dados**  
![SQLite](https://img.shields.io/badge/SQLite-3.37%2B-003B57?logo=sqlite)
![Pandas](https://img.shields.io/badge/Pandas-2.0%2B-150458)

**Infraestrutura**  
![Docker](https://img.shields.io/badge/Docker-24.0%2B-2496ED?logo=docker)
![YAML](https://img.shields.io/badge/YAML-1.2%2B-FF0000)

## 🏁 Começando

### Pré-requisitos
- Python 3.11+
- Docker 24.0+ (opcional)
- Credenciais da API do Reddit
- Chave da API OpenAI

### Instalação

**Ambiente Local:**
```bash
# Clonar repositório
git clone https://github.com/marcostolosa/oscp-insights.git
cd oscp-insights

# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar ambiente
cp .env.example .env
nano .env  # Adicione suas credenciais
```

**Docker Rápido:**
```bash
docker build -t oscp-insights .
docker run -p 8501:8501 --env-file .env oscp-insights
```

## ⚙️ Configuração

**config.yaml**
```yaml
# Parâmetros
post_min_length: 700  # Mínimo de caracteres
max_pagination: 5     # Paginação da API

# Busca
subreddit: "oscp"
search_query: "passed"
time_filter: "year"

# IA
openai:
  model: "gpt-4o"
  max_tokens: 6000
  temperature: 0.3
```

**.env**
```env
REDDIT_CLIENT_ID=seu_client_id
REDDIT_CLIENT_SECRET=seu_client_secret
REDDIT_USER_AGENT="script:OSCPInsights:v1.0 (by /u/seuusuario)"
OPENAI_API_KEY=sk-sua-chave
```

## 🖥️ Uso

**Execução Básica:**
```bash
# Coletar dados
python oscpInsights.py

# Iniciar dashboard
streamlit run dashboard.py
```

**Opções Avançadas:**
```bash
# Caminho personalizado do banco
python oscpInsights.py --dbpath /caminho/oscp_data.db

# Limitar por ano
python oscpInsights.py --year 2024
```

## 📊 Dashboard
**Funcionalidades Principais**
- 📈 **Métricas**
  - Volume de posts/comentários
  - Engajamento temporal
- 🔍 **Exploração**
  - Navegador de posts
  - Análise de sentimentos
  - Frequência de termos
- 📑 **Relatórios**
  - Análises estratégicas
  - Checklist para exame

**Acesso:** `http://localhost:8501`

## 🐳 Docker

**Produção:**
```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  analisador:
    image: oscp-insights:latest
    volumes:
      - dados_oscp:/app/data
    environment:
      - REDDIT_CLIENT_ID=${REDDIT_CLIENT_ID}
      - REDDIT_CLIENT_SECRET=${REDDIT_CLIENT_SECRET}
      - OPENAI_API_KEY=${OPENAI_API_KEY}

  dashboard:
    image: oscp-insights:latest
    ports:
      - "8501:8501"
    command: streamlit run dashboard.py
    depends_on:
      - analisador

volumes:
  dados_oscp:
```

**Implantação:**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## 🚨 Solução de Problemas

**Problemas Comuns:**
```bash
# Erro no banco de dados
rm oscp_posts.db && python oscpInsights.py

# Autenticação API
echo $REDDIT_CLIENT_ID  # Verificar variáveis
docker system prune  # Limpar cache
```

**Modo Debug:**
```bash
python oscpInsights.py --debug
```

## 🤝 Contribuição

Siga estas etapas:
1. Faça um fork
2. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
3. Commit: `git commit -m 'feat: adiciona análise avançada'`
4. Push: `git push origin feature/nova-funcionalidade`
5. Abra um Pull Request

