---
title: DarGlobal & Wasalt AI Assistant
emoji: 🏢
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# DarGlobal & Wasalt — AI Real Estate Chatbot

An AI-powered real estate assistant built with **FastAPI**, **Hybrid RAG (BM25 + TF-IDF)**, and **OpenRouter free models**, grounded in publicly scraped data from **[DarGlobal](https://darglobal.co.uk)** and **[Wasalt](https://wasalt.sa)**.

## Features

- **Public Web Scrapers (`app/scraper/`)**: Playwright + BeautifulSoup scrapers collecting public project portfolios, destinations, co-branded residences, company info, Saudi real estate listings, auctions, and district guides from DarGlobal and Wasalt.
- **Hybrid RAG Retrieval (`app/rag.py`)**: Combines BM25 lexical matching, word n-gram TF-IDF, character n-gram TF-IDF, and metadata/entity boosting with clickable source citations on every answer.
- **OpenRouter Free Models (`app/llm.py`)**: Uses `openrouter/free` by default with live free-model discovery (`/api/models`) and automatic fallback across active `:free` models if rate-limited.
- **Interactive Web UI (`static/`)**: Luxury real-estate chat interface with source filtering (`All`, `DarGlobal`, `Wasalt`), model switcher, citation chips, and a searchable **Scraped Knowledge Base Explorer**.
- **Docker & Hugging Face Spaces Ready**: Single lightweight container listening on port `7860` with healthchecks and non-root execution.

## Quick Start (Docker)

1. Copy `.env.example` to `.env` and add your free OpenRouter API key (get one at [openrouter.ai/keys](https://openrouter.ai/keys)):
   ```bash
   cp .env.example .env
   ```
2. Build and run with Docker Compose:
   ```bash
   docker compose up --build
   ```
3. Open `http://localhost:7860` in your browser.

## Local Development (Python / uv)

```bash
uv venv .venv --python 3.13
uv pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

### Re-running the Web Scraper

To refresh `data/knowledge_base.json` with newly scraped public pages from DarGlobal and Wasalt:

```bash
uv pip install -r requirements-scraper.txt
python -m app.scraper.run_scraper
```

## Deploying with Docker (Free Hosting Options)

### Option 1: Render (Recommended — Free, No Credit Card)
1. Push this repository to GitHub.
2. Go to [Render](https://dashboard.render.com) → **New + → Blueprint** (uses `render.yaml`) or **New + → Web Service** and select your repo.
3. Choose **Docker** runtime and the **Free** plan.
4. Add environment variable:
   - `OPENROUTER_API_KEY` = your free OpenRouter API key (`sk-or-v1-...` from [openrouter.ai/keys](https://openrouter.ai/keys))
5. Deploy — Render builds the `Dockerfile` and exposes your live public URL (`https://<service-name>.onrender.com`).

### Option 2: Railway / Back4App Containers / Google Cloud Run
Because `Dockerfile` reads `${PORT:-7860}` automatically, the same container deploys out-of-the-box on **Railway**, **Back4App Containers**, or **Google Cloud Run** by setting `OPENROUTER_API_KEY`.

## API Endpoints

- `GET /` — Interactive chatbot UI
- `GET /api/health` — Container health & index status
- `GET /api/models` — Live list of available OpenRouter `:free` models
- `GET /api/knowledge` — Scraped dataset statistics and document catalog
- `POST /api/chat` — RAG-grounded chat completion with source citations
- `GET /docs` — Interactive OpenAPI (Swagger) documentation
