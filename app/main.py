"""FastAPI application serving the DarGlobal & Wasalt AI Real Estate Chatbot."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, settings
from app.llm import OpenRouterClient, OpenRouterError
from app.models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    KnowledgeStats,
    ModelOption,
)
from app.rag import HybridRAGIndex

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

rag_index = HybridRAGIndex()
llm_client = OpenRouterClient()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load the scraped knowledge base index on application startup."""
    rag_index.load_from_file(settings.knowledge_base_path)
    logger.info(
        "Loaded %d documents (%d chunks) from %s",
        len(rag_index.documents),
        len(rag_index.chunks),
        settings.knowledge_base_path,
    )
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered real estate assistant built on publicly scraped data from "
        "DarGlobal and Wasalt, powered by OpenRouter free models."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _build_retrieval_query(request: ChatRequest) -> str:
    """Enrich short follow-up questions with the last user turn for better RAG recall."""
    msg = request.message.strip()
    if len(msg.split()) <= 8 and request.history:
        prior_users = [m.content for m in request.history if m.role == "user"]
        if prior_users:
            return f"{prior_users[-1]} {msg}"
    return msg


@app.get("/", include_in_schema=False)
async def serve_frontend() -> FileResponse:
    """Serve the chatbot single-page frontend."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)


@app.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness and readiness check for Docker & Hugging Face Spaces."""
    return HealthResponse(
        status="ok",
        documents_loaded=len(rag_index.documents),
        chunks_indexed=len(rag_index.chunks),
        openrouter_configured=bool(settings.openrouter_api_key.strip()),
        default_model=settings.openrouter_model,
    )


@app.get("/api/models", response_model=list[ModelOption])
async def get_free_models() -> list[ModelOption]:
    """Return currently available free models from OpenRouter."""
    return await llm_client.list_free_models()


@app.get("/api/knowledge", response_model=KnowledgeStats)
async def get_knowledge_stats() -> KnowledgeStats:
    """Return scraped dataset statistics and document catalog."""
    return rag_index.get_stats()


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    x_openrouter_key: str | None = Header(default=None),
) -> ChatResponse:
    """Retrieve grounded DarGlobal/Wasalt context and generate an AI response."""
    retrieval_query = _build_retrieval_query(request)
    hits = rag_index.retrieve(
        query=retrieval_query,
        top_k=settings.top_k_chunks,
        source_filter=request.source_filter,
    )
    citations = rag_index.to_citations(hits)

    # Only allow client-supplied key override when server key is unset
    api_key_override = None
    if not settings.openrouter_api_key.strip() and x_openrouter_key:
        api_key_override = x_openrouter_key.strip()

    try:
        answer, model_used = await llm_client.generate_answer(
            question=request.message,
            hits=hits,
            history=request.history,
            requested_model=request.model,
            api_key_override=api_key_override,
        )
    except OpenRouterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return ChatResponse(
        answer=answer,
        model_used=model_used,
        citations=citations,
        retrieved_count=len(hits),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
