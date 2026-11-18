"""Tests for the DarGlobal & Wasalt AI Real Estate Assistant."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from app.config import settings
from app.main import app, rag_index


def test_knowledge_base_loaded():
    rag_index.load_from_file(settings.knowledge_base_path)
    assert len(rag_index.documents) >= 30
    sources = {d["source"] for d in rag_index.documents}
    assert "darglobal" in sources
    assert "wasalt" in sources


def test_hybrid_retrieval_darglobal_and_wasalt():
    rag_index.load_from_file(settings.knowledge_base_path)

    dg_hits = rag_index.retrieve("DarGlobal luxury projects AIDA Oman Marbella", top_k=4)
    assert len(dg_hits) > 0
    assert any(c.source == "darglobal" for c, _ in dg_hits)

    ws_hits = rag_index.retrieve("Wasalt Saudi Arabia real estate auctions Shabeek", top_k=4)
    assert len(ws_hits) > 0
    assert any(c.source == "wasalt" for c, _ in ws_hits)

    # Source filter strictly isolates results
    only_ws = rag_index.retrieve("luxury villas", top_k=5, source_filter="wasalt")
    assert len(only_ws) > 0
    assert all(c.source == "wasalt" for c, _ in only_ws)


def test_api_endpoints_and_chat_flow():
    async def _run():
        rag_index.load_from_file(settings.knowledge_base_path)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/api/health")
            assert health.status_code == 200
            body = health.json()
            assert body["status"] == "ok"
            assert body["documents_loaded"] >= 30
            assert body["chunks_indexed"] >= 100

            kb = await client.get("/api/knowledge")
            assert kb.status_code == 200
            kb_data = kb.json()
            assert kb_data["darglobal_documents"] >= 20
            assert kb_data["wasalt_documents"] >= 10

            homepage = await client.get("/")
            assert homepage.status_code == 200
            assert "DarGlobal" in homepage.text
            assert "Wasalt" in homepage.text

            # Verify /api/chat integrates RAG retrieval + citations cleanly
            with patch(
                "app.main.llm_client.generate_answer",
                new=AsyncMock(
                    return_value=(
                        "DarGlobal develops AIDA in Oman, while Wasalt is a REGA-licensed Saudi real estate platform.",
                        "openrouter/free",
                    )
                ),
            ):
                chat_resp = await client.post(
                    "/api/chat",
                    json={"message": "Compare DarGlobal AIDA and Wasalt auctions", "source_filter": "all"},
                )
                assert chat_resp.status_code == 200
                chat_data = chat_resp.json()
                assert chat_data["model_used"] == "openrouter/free"
                assert chat_data["retrieved_count"] > 0
                assert len(chat_data["citations"]) > 0

    asyncio.run(_run())
