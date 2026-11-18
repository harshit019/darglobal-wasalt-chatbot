"""Public data scraper for Wasalt (wasalt.sa & official public partner/ecosystem sources)."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)


WASALT_PUBLIC_WEB_PAGES: list[dict[str, str]] = [
    {
        "id": "wasalt-quara-profile",
        "title": "Wasalt Official Profile — Quara Holding (REGA-Licensed Saudi PropTech)",
        "url": "https://quaraholding.com/en/investments/wasalt",
        "category": "Corporate Profile",
        "location": "Saudi Arabia",
        "brand": "Wasalt / Quara Holding",
    },
    {
        "id": "wasalt-daralarkan-ecosystem",
        "title": "Dar Al Arkan & Quara Holding Ecosystem (Wasalt & DarGlobal Group)",
        "url": "https://quaraholding.com/en/investments/daralarkan",
        "category": "Group Ecosystem",
        "location": "Saudi Arabia",
        "brand": "Dar Al Arkan / Quara Holding",
    },
    {
        "id": "wasalt-cire-partnership",
        "title": "Wasalt Brokerage × Christie's International Real Estate Saudi Arabia",
        "url": "https://cire-saudi.com/",
        "category": "Luxury Brokerage Partnership",
        "location": "Riyadh & Jeddah, Saudi Arabia",
        "brand": "Wasalt × Christie's International Real Estate",
    },
    {
        "id": "wasalt-cire-about",
        "title": "About Christie's International Real Estate Saudi Arabia (Wasalt Partner)",
        "url": "https://cire-saudi.com/about",
        "category": "Luxury Brokerage Partnership",
        "location": "Saudi Arabia",
        "brand": "Wasalt × Christie's International Real Estate",
    },
    {
        "id": "wasalt-cire-projects",
        "title": "Luxury Saudi Projects Represented via Wasalt Brokerage & Christie's Saudi",
        "url": "https://cire-saudi.com/projects",
        "category": "Projects & Developments",
        "location": "Riyadh & Jeddah, Saudi Arabia",
        "brand": "Wasalt × Christie's International Real Estate",
    },
    {
        "id": "wasalt-project-amaya",
        "title": "Amaya Plots Jeddah — Listed via Wasalt Brokerage & Christie's Saudi",
        "url": "https://cire-saudi.com/projects/amaya-plots",
        "category": "Saudi Project Listing",
        "location": "Jeddah, Saudi Arabia",
        "brand": "Wasalt Brokerage",
    },
    {
        "id": "wasalt-project-elevee",
        "title": "Elevee Al Nakhil, Riyadh — Listed via Wasalt Brokerage & Christie's Saudi",
        "url": "https://cire-saudi.com/projects/elevee",
        "category": "Saudi Project Listing",
        "location": "Al Nakhil, Riyadh, Saudi Arabia",
        "brand": "Wasalt Brokerage",
    },
    {
        "id": "wasalt-project-padel-living",
        "title": "Padel Living Residences, Jeddah — Listed via Wasalt Brokerage & Christie's Saudi",
        "url": "https://cire-saudi.com/projects/padel-living",
        "category": "Saudi Project Listing",
        "location": "Jeddah, Saudi Arabia",
        "brand": "Wasalt Brokerage",
    },
    {
        "id": "wasalt-project-trump-park",
        "title": "Trump Park Residences, Amaya Jeddah — Listed via Wasalt Brokerage",
        "url": "https://cire-saudi.com/projects/trump-park-residences",
        "category": "Saudi Project Listing",
        "location": "Jeddah, Saudi Arabia",
        "brand": "Wasalt Brokerage",
    },
    {
        "id": "wasalt-project-trump-tower-jeddah",
        "title": "Trump Tower Jeddah — Listed via Wasalt Brokerage & Christie's Saudi",
        "url": "https://cire-saudi.com/projects/trump-tower",
        "category": "Saudi Project Listing",
        "location": "Jeddah, Saudi Arabia",
        "brand": "Wasalt Brokerage",
    },
]

WASALT_DIRECT_PAGES: list[dict[str, str]] = [
    {
        "id": "wasalt-home",
        "title": "Wasalt Platform Overview — Properties for Sale, Rent, Projects & Auctions",
        "url": "https://wasalt.sa/en",
        "category": "Platform Overview",
        "location": "Saudi Arabia (Riyadh, Jeddah, Makkah, Madinah, Dammam, Al Khobar)",
        "brand": "Wasalt",
    },
]


def _clean_html_text(html: str) -> str:
    """Extract clean readable text from HTML while removing boilerplate."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "form"]):
        tag.decompose()

    lines: list[str] = []
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        desc = str(meta_desc["content"]).strip()
        if len(desc) >= 20:
            lines.append(f"Overview: {desc}")

    main = soup.find("main") or soup.body or soup
    seen: set[str] = set()
    skip_phrases = (
        "privacy policy",
        "terms of use",
        "all rights reserved",
        "cookie",
        "register your interest",
        "please provide your details",
        "first name",
        "last name",
    )

    for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
        if len(txt) < 18 or len(txt) > 1400:
            continue
        low = txt.lower()
        if any(s in low for s in skip_phrases):
            continue
        if txt not in seen:
            seen.add(txt)
            lines.append(txt)

    if len(lines) < 4:
        full_text = re.sub(r"\s+", " ", main.get_text(" ", strip=True)).strip()
        if len(full_text) >= 120:
            lines.append(full_text[:4500])

    return "\n\n".join(lines[:50])[:6500]


async def _scrape_wasalt_direct_home(context: BrowserContext) -> list[dict[str, Any]]:
    """Scrape https://wasalt.sa/en directly via Playwright when publicly accessible."""
    docs: list[dict[str, Any]] = []
    for item in WASALT_DIRECT_PAGES:
        page = await context.new_page()
        try:
            logger.info("Scraping Wasalt direct page: %s", item["url"])
            resp = await page.goto(item["url"], wait_until="domcontentloaded", timeout=35000)
            status = resp.status if resp else 0
            await page.wait_for_timeout(4000)
            title = (await page.title()).strip()
            html = await page.content()

            if status >= 400 or "just a moment" in title.lower():
                logger.warning("Wasalt direct page returned challenge/status %s: %s", status, item["url"])
                continue

            content = _clean_html_text(html)
            if len(content.strip()) >= 120:
                docs.append(
                    {
                        "id": item["id"],
                        "source": "wasalt",
                        "category": item["category"],
                        "title": item["title"],
                        "page_title": title,
                        "url": item["url"],
                        "location": item["location"],
                        "brand": item["brand"],
                        "tags": ["Wasalt", "Saudi Arabia", "Riyadh", "Jeddah", "Makkah", "Madinah", "Dammam", "Al Khobar"],
                        "content": content,
                    }
                )
        except Exception as exc:
            logger.warning("Failed scraping Wasalt direct %s: %s", item["url"], exc)
        finally:
            await page.close()
    return docs


async def _scrape_wasalt_official_apps() -> list[dict[str, Any]]:
    """Fetch official first-party Wasalt & Wasalt Business app listings from Apple App Store API."""
    docs: list[dict[str, Any]] = []
    endpoints = [
        (
            "wasalt-app-consumer",
            "Wasalt App — Property Search, Projects, Land Plans, Electronic Auctions & Shabeek Matchmaker",
            "https://itunes.apple.com/lookup?id=1588885673&country=us",
            "Mobile App & Services",
            "https://wasalt.sa/en",
        ),
        (
            "wasalt-app-business",
            "Wasalt Business (وصلت أعمال) — Broker CRM, Exclusive Projects & Wasalt Ambassadors",
            "https://itunes.apple.com/lookup?id=1663527328&country=sa",
            "Broker & Developer Platform",
            "https://business.wasalt.sa/en/login",
        ),
    ]

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for doc_id, title, api_url, category, public_url in endpoints:
            try:
                resp = await client.get(api_url)
                resp.raise_for_status()
                results = resp.json().get("results") or []
                if not results:
                    continue
                app = results[0]
                desc = str(app.get("description", "")).strip()
                seller = str(app.get("sellerName", "Wasalt")).strip()
                rating = app.get("averageUserRating")
                rating_count = app.get("userRatingCount")
                store_url = str(app.get("trackViewUrl") or public_url)

                header = [
                    f"Application: {app.get('trackName', title)}",
                    f"Publisher: {seller}",
                    f"Category: {app.get('primaryGenreName', 'Real Estate')}",
                ]
                if rating:
                    header.append(f"App Store Rating: {round(float(rating), 2)}/5 ({rating_count} ratings)")
                content = "\n".join(header) + "\n\n" + desc

                if doc_id == "wasalt-app-business":
                    content += (
                        "\n\nEnglish Summary of Wasalt Business Features:\n"
                        "- Dedicated Saudi real estate platform for real estate offices, brokers, and property marketers.\n"
                        "- Connects brokers and marketers with a large base of verified property seekers and client requests.\n"
                        "- Enables brokers to manage client leads, property listings, and daily business workflows.\n"
                        "- Provides instant access to exclusive Wasalt developer projects across Saudi Arabia.\n"
                        "- Offers enrollment in the Wasalt Ambassadors program for real estate professionals."
                    )

                docs.append(
                    {
                        "id": doc_id,
                        "source": "wasalt",
                        "category": category,
                        "title": title,
                        "page_title": str(app.get("trackName", title)),
                        "url": store_url,
                        "location": "Saudi Arabia (Riyadh, Jeddah, Dammam, Al Khobar)",
                        "brand": "Wasalt",
                        "tags": ["Wasalt", "Wasalt Business", "Auctions", "Shabeek", "Matchmaker", "Saudi Arabia"],
                        "content": content[:6500],
                    }
                )
            except Exception as exc:
                logger.warning("Failed fetching Wasalt app metadata %s: %s", api_url, exc)

    return docs


async def _scrape_wasalt_partner_pages() -> list[dict[str, Any]]:
    """Scrape public HTTP-accessible official parent (Quara Holding) and partner (CIRE Saudi) pages."""
    docs: list[dict[str, Any]] = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
    }

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
        for item in WASALT_PUBLIC_WEB_PAGES:
            try:
                logger.info("Scraping Wasalt public ecosystem page: %s", item["url"])
                resp = await client.get(item["url"])
                if resp.status_code >= 400:
                    logger.warning("HTTP %s on %s", resp.status_code, item["url"])
                    continue

                soup = BeautifulSoup(resp.text, "lxml")
                page_title = soup.title.get_text(strip=True) if soup.title else item["title"]
                content = _clean_html_text(resp.text)
                if len(content.strip()) < 100:
                    continue

                docs.append(
                    {
                        "id": item["id"],
                        "source": "wasalt",
                        "category": item["category"],
                        "title": item["title"],
                        "page_title": page_title,
                        "url": item["url"],
                        "location": item["location"],
                        "brand": item["brand"],
                        "tags": ["Wasalt", "Saudi Arabia", item["category"], item["location"]],
                        "content": content,
                    }
                )
            except Exception as exc:
                logger.warning("Failed scraping %s: %s", item["url"], exc)

    return docs


async def scrape_wasalt(context: BrowserContext) -> list[dict[str, Any]]:
    """Scrape public Wasalt platform, app store, corporate, and brokerage partner pages."""
    direct_docs = await _scrape_wasalt_direct_home(context)
    app_docs = await _scrape_wasalt_official_apps()
    ecosystem_docs = await _scrape_wasalt_partner_pages()

    docs = direct_docs + app_docs + ecosystem_docs
    logger.info("Scraped %d Wasalt documents.", len(docs))
    return docs
