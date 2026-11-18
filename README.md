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

## Deploying to Hugging Face Spaces (Free Docker Hosting)

1. Create a new Space on [Hugging Face Spaces](https://huggingface.co/new-space) and select **Docker** as the SDK (Blank template).
2. In the Space **Settings → Variables and secrets**, add a **New secret**:
   - Name: `OPENROUTER_API_KEY`
   - Value: your free OpenRouter API key (`sk-or-v1-...`)
3. Push this repository to your Hugging Face Space:
   ```bash
   git remote add hf https://huggingface.co/spaces/<your-username>/<your-space-name>
   git push hf main
   ```
4. Hugging Face automatically builds the `Dockerfile` and exposes your live chatbot at `https://<your-username>-<your-space-name>.hf.space`.

## API Endpoints

- `GET /` — Interactive chatbot UI
- `GET /api/health` — Container health & index status
- `GET /api/models` — Live list of available OpenRouter `:free` models
- `GET /api/knowledge` — Scraped dataset statistics and document catalog
- `POST /api/chat` — RAG-grounded chat completion with source citations
- `GET /docs` — Interactive OpenAPI (Swagger) documentation
