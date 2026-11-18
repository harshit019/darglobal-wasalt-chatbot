"""CLI entrypoint to scrape public data from DarGlobal and Wasalt into data/knowledge_base.json."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

from app.config import settings
from app.scraper.darglobal import scrape_darglobal
from app.scraper.wasalt import scrape_wasalt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def _launch_browser(playwright):
    """Launch Microsoft Edge locally if installed, otherwise default Playwright Chromium."""
    launch_args = ["--disable-blink-features=AutomationControlled"]
    try:
        return await playwright.chromium.launch(
            channel="msedge", headless=True, args=launch_args
        )
    except Exception:
        return await playwright.chromium.launch(headless=True, args=launch_args)


async def run_all_scrapers(
    output_path: Path | None = None,
    only: str | None = None,
    merge: bool = False,
) -> dict:
    """Run DarGlobal and/or Wasalt scrapers and persist the combined JSON dataset."""
    target_path = output_path or settings.knowledge_base_path
    target_path.parent.mkdir(parents=True, exist_ok=True)

    existing_by_id: dict[str, dict] = {}
    if merge and target_path.exists():
        old_payload = json.loads(target_path.read_text(encoding="utf-8"))
        for doc in old_payload.get("documents", []):
            existing_by_id[str(doc.get("id"))] = doc

    darglobal_docs: list[dict] = []
    wasalt_docs: list[dict] = []

    async with async_playwright() as p:
        browser = await _launch_browser(p)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
            ),
            locale="en-US",
        )
        try:
            if only in (None, "darglobal"):
                darglobal_docs = await scrape_darglobal(context)
            if only in (None, "wasalt"):
                wasalt_docs = await scrape_wasalt(context)
        finally:
            await browser.close()

    if merge:
        for doc in darglobal_docs + wasalt_docs:
            existing_by_id[str(doc["id"])] = doc
        all_docs = list(existing_by_id.values())
    else:
        all_docs = darglobal_docs + wasalt_docs

    dg_total = sum(1 for d in all_docs if d.get("source") == "darglobal")
    ws_total = sum(1 for d in all_docs if d.get("source") == "wasalt")

    payload = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "darglobal": {
                "base_url": "https://darglobal.co.uk",
                "document_count": dg_total,
            },
            "wasalt": {
                "base_url": "https://wasalt.sa/en",
                "document_count": ws_total,
            },
        },
        "total_documents": len(all_docs),
        "documents": all_docs,
    }

    target_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(
        "Saved %d total documents (%d DarGlobal, %d Wasalt) to %s",
        len(all_docs),
        dg_total,
        ws_total,
        target_path,
    )
    return payload


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Scrape DarGlobal & Wasalt public data")
    parser.add_argument("--only", choices=["darglobal", "wasalt"], default=None)
    parser.add_argument("--merge", action="store_true", help="Merge with existing knowledge_base.json")
    args = parser.parse_args()

    asyncio.run(run_all_scrapers(only=args.only, merge=args.merge))


if __name__ == "__main__":
    main()
