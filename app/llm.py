"""OpenRouter LLM client using free models with dynamic discovery and automatic fallback."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.config import settings
from app.models import ChatMessage, ModelOption
from app.rag import IndexedChunk

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are the DarGlobal & Wasalt Real Estate AI Assistant.
You answer user questions accurately using ONLY the scraped public data provided in the Context section below from DarGlobal (darglobal.co.uk) and Wasalt (wasalt.sa).

Rules:
1. Ground every factual claim (projects, locations, partner brands, property types, prices, amenities, company facts, auctions, services) strictly in the provided Context.
2. When referencing projects, listings, or services, mention whether they belong to **DarGlobal** or **Wasalt**, and include relevant details such as location, partner brand, starting price, or property type when present in the context.
3. Use clean, structured Markdown (short bullet points, bold project names, concise comparison tables when comparing multiple properties or comparing DarGlobal vs. Wasalt).
4. If the user asks something not covered in the scraped context, clearly say what information is not available in the collected dataset and suggest related topics you can help with. Never invent prices, unit counts, or contact numbers.
5. Keep responses helpful, clear, and well-organized. Respond in the same language as the user (English or Arabic) when appropriate."""


class OpenRouterError(Exception):
    """Raised when OpenRouter fails across all attempted free models."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class OpenRouterClient:
    """Async client for OpenRouter chat completions with free-model caching & fallback."""

    def __init__(self) -> None:
        self._cached_models: list[ModelOption] = []
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 1800.0  # 30 minutes

    async def list_free_models(self) -> list[ModelOption]:
        """Fetch currently active free models from OpenRouter (with local fallback)."""
        now = time.time()
        if self._cached_models and (now - self._cache_timestamp) < self._cache_ttl:
            return self._cached_models

        defaults = [
            ModelOption(id="openrouter/free", name="OpenRouter Free (Auto-Router)", context_length=200000),
            ModelOption(id="google/gemma-4-31b-it:free", name="Google Gemma 4 31B (Free)", context_length=262144),
            ModelOption(id="google/gemma-4-26b-a4b-it:free", name="Google Gemma 4 26B A4B (Free)", context_length=262144),
            ModelOption(id="nvidia/nemotron-3.5-lightning:free", name="NVIDIA Nemotron 3.5 Lightning (Free)", context_length=1000000),
            ModelOption(id="nvidia/nemotron-3-ultra-550b-a55b:free", name="NVIDIA Nemotron 3 Ultra 550B (Free)", context_length=1000000),
            ModelOption(id="inclusionai/ling-3.2-flash:free", name="Ling 3.2 Flash (Free)", context_length=1048576),
        ]

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(f"{settings.openrouter_base_url}/models")
                resp.raise_for_status()
                data = resp.json().get("data", [])

            discovered: list[ModelOption] = []
            for item in data:
                model_id = str(item.get("id", ""))
                pricing = item.get("pricing") or {}
                is_zero_price = (
                    str(pricing.get("prompt", "")) in ("0", "0.0")
                    and str(pricing.get("completion", "")) in ("0", "0.0")
                )
                if model_id == "openrouter/free" or model_id.endswith(":free") or is_zero_price:
                    discovered.append(
                        ModelOption(
                            id=model_id,
                            name=str(item.get("name") or model_id),
                            context_length=item.get("context_length"),
                        )
                    )

            if discovered:
                # Place openrouter/free first, then strong well-known chat models
                discovered.sort(
                    key=lambda m: (
                        0 if m.id == "openrouter/free"
                        else 1 if "gemma" in m.id.lower()
                        else 2 if "nemotron" in m.id.lower()
                        else 3,
                        m.id,
                    )
                )
                self._cached_models = discovered
                self._cache_timestamp = now
                return discovered
        except Exception as exc:
            logger.warning("Could not refresh live OpenRouter free models: %s", exc)

        self._cached_models = defaults
        self._cache_timestamp = now
        return defaults

    def _build_context_block(self, hits: list[tuple[IndexedChunk, float]]) -> str:
        """Format retrieved RAG chunks into a numbered context block for the LLM."""
        if not hits:
            return "No matching documents were retrieved from the scraped dataset."

        blocks: list[str] = []
        for idx, (chunk, score) in enumerate(hits, start=1):
            source_label = "DarGlobal" if chunk.source == "darglobal" else "Wasalt"
            meta = [f"Source: {source_label}", f"Category: {chunk.category}"]
            if chunk.location:
                meta.append(f"Location: {chunk.location}")
            if chunk.brand:
                meta.append(f"Brand: {chunk.brand}")
            if chunk.url:
                meta.append(f"URL: {chunk.url}")

            blocks.append(
                f"[{idx}] {chunk.title} ({' | '.join(meta)})\n{chunk.text}"
            )
        return "\n\n---\n\n".join(blocks)

    async def generate_answer(
        self,
        question: str,
        hits: list[tuple[IndexedChunk, float]],
        history: list[ChatMessage],
        requested_model: str | None = None,
        api_key_override: str | None = None,
    ) -> tuple[str, str]:
        """Generate a grounded response via OpenRouter with automatic free-model fallback."""
        api_key = (api_key_override or settings.openrouter_api_key).strip()
        if not api_key:
            raise OpenRouterError(
                "OPENROUTER_API_KEY is not configured. Add a free OpenRouter API key in "
                "your environment / Hugging Face Space Secrets (or enter one in Settings) to chat.",
                status_code=400,
            )

        context_block = self._build_context_block(hits)
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": f"{SYSTEM_PROMPT}\n\n=== SCRAPED KNOWLEDGE CONTEXT ===\n{context_block}",
            }
        ]

        # Append bounded conversation history
        trimmed_history = history[-(settings.max_history_turns * 2) :]
        for turn in trimmed_history:
            messages.append({"role": turn.role, "content": turn.content})

        messages.append({"role": "user", "content": question})

        # Build candidate free model chain
        primary = (requested_model or settings.openrouter_model or "openrouter/free").strip()
        # Enforce free models only
        if primary != "openrouter/free" and not primary.endswith(":free"):
            primary = "openrouter/free"

        live_models = await self.list_free_models()
        candidate_ids: list[str] = [primary]
        for fallback_id in settings.fallback_free_models:
            if fallback_id not in candidate_ids:
                candidate_ids.append(fallback_id)
        for live in live_models[:6]:
            if live.id not in candidate_ids:
                candidate_ids.append(live.id)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.app_public_url,
            "X-Title": settings.app_name,
        }

        last_error = "OpenRouter request failed."
        last_status = 502

        async with httpx.AsyncClient(timeout=45.0) as client:
            for model_id in candidate_ids[:4]:
                payload: dict[str, Any] = {
                    "model": model_id,
                    "messages": messages,
                    "temperature": 0.25,
                    "max_tokens": 900,
                }
                try:
                    resp = await client.post(
                        f"{settings.openrouter_base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                except httpx.HTTPError as exc:
                    last_error = f"Network error calling OpenRouter ({model_id}): {exc}"
                    logger.warning(last_error)
                    continue

                if resp.status_code == 200:
                    body = resp.json()
                    choices = body.get("choices") or []
                    if choices:
                        content = (choices[0].get("message") or {}).get("content") or ""
                        if content.strip():
                            used_model = str(body.get("model") or model_id)
                            return content.strip(), used_model
                    last_error = f"Empty completion from {model_id}"
                    continue

                # Auth errors should fail immediately (retrying other models won't fix a bad key)
                if resp.status_code in (401, 403):
                    detail = self._extract_error(resp)
                    raise OpenRouterError(
                        f"OpenRouter authentication failed: {detail}",
                        status_code=resp.status_code,
                    )

                last_status = resp.status_code
                last_error = f"{model_id} returned HTTP {resp.status_code}: {self._extract_error(resp)}"
                logger.warning("Fallback triggered — %s", last_error)

        raise OpenRouterError(
            f"All free OpenRouter models are currently unavailable or rate-limited. Last error: {last_error}",
            status_code=last_status if last_status in (429, 502, 503) else 502,
        )

    @staticmethod
    def _extract_error(resp: httpx.Response) -> str:
        try:
            err = resp.json().get("error")
            if isinstance(err, dict):
                return str(err.get("message") or err)
            if err:
                return str(err)
        except Exception:
            pass
        return resp.text[:240]
