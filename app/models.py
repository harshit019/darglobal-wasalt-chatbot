"""Pydantic models for API requests, responses, and knowledge base records."""

from typing import Literal
from pydantic import BaseModel, Field


SourceName = Literal["all", "darglobal", "wasalt"]


class ChatMessage(BaseModel):
    """A single conversational turn."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    """Incoming chat completion request from the UI or API client."""

    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    source_filter: SourceName = "all"
    model: str | None = None


class Citation(BaseModel):
    """Reference to a scraped document chunk used to ground an answer."""

    title: str
    url: str
    source: Literal["darglobal", "wasalt"]
    category: str
    snippet: str
    score: float


class ChatResponse(BaseModel):
    """Structured chatbot reply with model metadata and citations."""

    answer: str
    model_used: str
    citations: list[Citation] = Field(default_factory=list)
    retrieved_count: int = 0


class ModelOption(BaseModel):
    """Free OpenRouter model metadata."""

    id: str
    name: str
    context_length: int | None = None


class KnowledgeDocSummary(BaseModel):
    """Compact view of a scraped document for the Knowledge Explorer."""

    id: str
    source: Literal["darglobal", "wasalt"]
    category: str
    title: str
    url: str
    location: str | None = None
    brand: str | None = None
    summary: str


class KnowledgeStats(BaseModel):
    """Aggregate stats of the scraped knowledge base."""

    total_documents: int
    total_chunks: int
    darglobal_documents: int
    wasalt_documents: int
    scraped_at: str
    categories: dict[str, int]
    documents: list[KnowledgeDocSummary]


class HealthResponse(BaseModel):
    """Health check payload."""

    status: str
    documents_loaded: int
    chunks_indexed: int
    openrouter_configured: bool
    default_model: str
