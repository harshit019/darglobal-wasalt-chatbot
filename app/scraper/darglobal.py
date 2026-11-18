"""Public data scraper for DarGlobal (darglobal.co.uk) using Playwright + BeautifulSoup."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)


DARGLOBAL_CORE_PAGES: list[dict[str, str | None]] = [
    {
        "id": "dg-home",
        "title": "DarGlobal — Company Overview & Key Figures",
        "url": "https://darglobal.co.uk/",
        "category": "Company Overview",
        "location": "Global (UAE, Saudi Arabia, Oman, Qatar, Spain, UK)",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-about",
        "title": "About DarGlobal — Vision, Portfolio & Track Record",
        "url": "https://darglobal.co.uk/about",
        "category": "About & Corporate",
        "location": "London & Global Markets",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-investor",
        "title": "DarGlobal Investor Relations (London Stock Exchange)",
        "url": "https://darglobal.co.uk/investor",
        "category": "Investor Relations",
        "location": "London, UK",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-why-invest",
        "title": "Why Invest with DarGlobal",
        "url": "https://darglobal.co.uk/why-invest",
        "category": "Investment Guide",
        "location": "Global Markets",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-faq",
        "title": "DarGlobal Frequently Asked Questions (FAQ)",
        "url": "https://darglobal.co.uk/faq",
        "category": "FAQ",
        "location": "Global",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-projects",
        "title": "DarGlobal Luxury Real Estate Projects Directory",
        "url": "https://darglobal.co.uk/projects",
        "category": "Projects Directory",
        "location": "Global",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-golf",
        "title": "DarGlobal Luxury Golf Communities",
        "url": "https://darglobal.co.uk/luxury-golf-communities",
        "category": "Lifestyle & Communities",
        "location": "Oman, Qatar, Saudi Arabia",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-hospitality",
        "title": "DarGlobal Luxury Hospitality & Branded Hotels",
        "url": "https://darglobal.co.uk/hospitality",
        "category": "Hospitality",
        "location": "Global",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-tokenization",
        "title": "DarGlobal Real Estate Tokenization",
        "url": "https://darglobal.co.uk/tokenization",
        "category": "Innovation & Asset Management",
        "location": "Global",
        "brand": "DarGlobal",
    },
]

DARGLOBAL_REGION_PAGES: list[dict[str, str | None]] = [
    {
        "id": "dg-uae",
        "title": "DarGlobal Luxury Properties in the UAE (Dubai & Ras Al Khaimah)",
        "url": "https://darglobal.co.uk/projects/properties-in-uae",
        "category": "Regional Portfolio",
        "location": "United Arab Emirates",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-saudi",
        "title": "DarGlobal Luxury Properties in Saudi Arabia (Riyadh & Jeddah)",
        "url": "https://darglobal.co.uk/projects/properties-in-saudi-arabia",
        "category": "Regional Portfolio",
        "location": "Saudi Arabia",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-oman",
        "title": "DarGlobal Luxury Properties in Oman (AIDA, Muscat)",
        "url": "https://darglobal.co.uk/projects/properties-in-oman",
        "category": "Regional Portfolio",
        "location": "Oman",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-qatar",
        "title": "DarGlobal Luxury Properties in Qatar (Doha & Simaisma)",
        "url": "https://darglobal.co.uk/projects/properties-in-qatar",
        "category": "Regional Portfolio",
        "location": "Qatar",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-spain",
        "title": "DarGlobal Luxury Properties in Spain (Marbella & Costa del Sol)",
        "url": "https://darglobal.co.uk/projects/properties-in-spain",
        "category": "Regional Portfolio",
        "location": "Spain",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-uk",
        "title": "DarGlobal Luxury Properties in the United Kingdom (London)",
        "url": "https://darglobal.co.uk/projects/properties-in-uk",
        "category": "Regional Portfolio",
        "location": "London, United Kingdom",
        "brand": "DarGlobal",
    },
]

DARGLOBAL_PARTNER_PAGES: list[dict[str, str | None]] = [
    {
        "id": "dg-partner-lamborghini",
        "title": "DarGlobal × Automobili Lamborghini (Tierra Viva, Marbella)",
        "url": "https://darglobal.co.uk/partners/lamborghini",
        "category": "Co-Branded Residences",
        "location": "Marbella, Spain",
        "brand": "Automobili Lamborghini",
    },
    {
        "id": "dg-partner-aston-martin",
        "title": "DarGlobal × Aston Martin (The Astera, Ras Al Khaimah)",
        "url": "https://darglobal.co.uk/partners/aston-martin",
        "category": "Co-Branded Residences",
        "location": "Al Marjan Island, Ras Al Khaimah, UAE",
        "brand": "Aston Martin",
    },
    {
        "id": "dg-partner-elie-saab",
        "title": "DarGlobal × Elie Saab Residences",
        "url": "https://darglobal.co.uk/partners/elie-saab",
        "category": "Co-Branded Residences",
        "location": "Qatar & Riyadh",
        "brand": "Elie Saab",
    },
    {
        "id": "dg-partner-fendi-casa",
        "title": "DarGlobal × Fendi Casa (Azure Oceanfront Villas, Oman)",
        "url": "https://darglobal.co.uk/partners/fendi-casa",
        "category": "Co-Branded Residences",
        "location": "Oman",
        "brand": "Fendi Casa",
    },
    {
        "id": "dg-partner-missoni",
        "title": "DarGlobal × Missoni (Urban Oasis Dubai & Marea Spain)",
        "url": "https://darglobal.co.uk/partners/missoni",
        "category": "Co-Branded Residences",
        "location": "Dubai, UAE & Costa del Sol, Spain",
        "brand": "Missoni",
    },
    {
        "id": "dg-partner-mouawad",
        "title": "DarGlobal × Mouawad (Neptune Villas, Riyadh)",
        "url": "https://darglobal.co.uk/partners/mouawad",
        "category": "Co-Branded Residences",
        "location": "Riyadh, Saudi Arabia",
        "brand": "Mouawad",
    },
    {
        "id": "dg-partner-pagani",
        "title": "DarGlobal × Pagani (Da Vinci Tower, Downtown Dubai)",
        "url": "https://darglobal.co.uk/partners/pagani",
        "category": "Co-Branded Residences",
        "location": "Downtown Dubai, UAE",
        "brand": "Pagani",
    },
    {
        "id": "dg-partner-trump",
        "title": "DarGlobal × The Trump Organization (Oman, Jeddah, Dubai, Qatar, Riyadh)",
        "url": "https://darglobal.co.uk/partners/the-trump-organization",
        "category": "Co-Branded Residences",
        "location": "Oman, Saudi Arabia, UAE, Qatar",
        "brand": "The Trump Organization",
    },
    {
        "id": "dg-partner-marriott",
        "title": "DarGlobal × Marriott Residences AIDA, Oman",
        "url": "https://darglobal.co.uk/partners/marriott-residences-aida-oman",
        "category": "Co-Branded Residences",
        "location": "AIDA, Muscat, Oman",
        "brand": "Marriott Residences",
    },
    {
        "id": "dg-partner-w-hotels",
        "title": "DarGlobal × W Residences Dubai",
        "url": "https://darglobal.co.uk/partners/w-hotels",
        "category": "Co-Branded Residences",
        "location": "Downtown Dubai, UAE",
        "brand": "W Hotels",
    },
]

DARGLOBAL_PRESS_PAGES: list[dict[str, str | None]] = [
    {
        "id": "dg-press-jeddah-2026",
        "title": "DarGlobal Expands Saudi Portfolio with SAR 1 Billion Jeddah Development (Nov 2026)",
        "url": "https://darglobal.co.uk/press/dar-global-expands-saudi-arabia-portfolio-with-new-jeddah-development-valued-at-sar-1-billion",
        "category": "Press Release",
        "location": "Jeddah, Saudi Arabia",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-press-hy2026",
        "title": "DarGlobal HY 2026 Financial Results — 66% Revenue Growth & $23B GDV",
        "url": "https://darglobal.co.uk/press/dar-global-delivers-66-percent-revenue-growth-hy-2026-portfolio-gdv-reaches-23-billion",
        "category": "Press Release",
        "location": "Global",
        "brand": "DarGlobal",
    },
    {
        "id": "dg-press-trump-qatar",
        "title": "DarGlobal Opens Sales for Trump Villas Simaisma, Qatar (Oct 2026)",
        "url": "https://darglobal.co.uk/press/dar-global-opens-sales-trump-villas-simaisma-qatar-unprecedented-interest",
        "category": "Press Release",
        "location": "Simaisma, Qatar",
        "brand": "The Trump Organization",
    },
    {
        "id": "dg-press-trump-dubai",
        "title": "DarGlobal Appoints Contractor for Trump International Hotel & Tower Dubai",
        "url": "https://darglobal.co.uk/press/dar-global-appoints-gulf-asia-contracting-for-trump-international-hotel-tower-dubai",
        "category": "Press Release",
        "location": "Dubai, UAE",
        "brand": "The Trump Organization",
    },
    {
        "id": "dg-press-fendi-oman",
        "title": "DarGlobal & Fendi Casa Announce Azure Oceanfront Villas in Oman",
        "url": "https://darglobal.co.uk/press/darglobal-fendi-casa-announce-azure-oceanfront-villas-oman",
        "category": "Press Release",
        "location": "AIDA, Muscat, Oman",
        "brand": "Fendi Casa",
    },
    {
        "id": "dg-aida-flagship",
        "title": "AIDA Oman — Cliffside Masterplan & Luxury Golf Community",
        "url": "https://darglobal.co.uk/landing-page/aida",
        "category": "Flagship Masterplan",
        "location": "Muscat, Oman",
        "brand": "DarGlobal",
    },
]


def _extract_clean_text(html: str, fallback_inner: str) -> str:
    """Clean extracted HTML + innerText into high-signal paragraphs."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "footer", "nav"]):
        tag.decompose()

    lines: list[str] = []
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        desc = str(meta_desc["content"]).strip()
        if len(desc) >= 20:
            lines.append(f"Summary: {desc}")

    seen: set[str] = set()
    skip_phrases = (
        "register interest",
        "cookie policy",
        "privacy policy",
        "terms of use",
        "anti slavery",
        "all rights reserved",
        "accept all cookies",
        "first name",
        "last name",
        "email address",
        "phone number",
    )

    for raw_line in fallback_inner.splitlines():
        txt = re.sub(r"\s+", " ", raw_line).strip()
        if len(txt) < 18 or len(txt) > 1400:
            continue
        low = txt.lower()
        if any(p in low for p in skip_phrases):
            continue
        if txt not in seen:
            seen.add(txt)
            lines.append(txt)

    return "\n\n".join(lines[:55])[:6800]


async def _scrape_single_page(
    context: BrowserContext, url: str
) -> tuple[str, str, list[tuple[str, str]]]:
    """Load a DarGlobal page, returning (title, cleaned_text, discovered_project_links)."""
    page = await context.new_page()
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        status = resp.status if resp else 0
        await page.wait_for_timeout(3500)
        html = await page.content()

        # First visit may set an Incapsula session cookie; reload once politely
        if "incapsula" in html.lower()[:500]:
            await page.wait_for_timeout(2500)
            resp = await page.reload(wait_until="domcontentloaded", timeout=35000)
            status = resp.status if resp else status
            await page.wait_for_timeout(3500)
            html = await page.content()

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.4)")
        await page.wait_for_timeout(1000)

        title = (await page.title()).strip()
        html = await page.content()
        inner = await page.evaluate("() => document.body ? document.body.innerText : ''")

        if status >= 400 or "incapsula" in html.lower()[:400]:
            logger.warning("DarGlobal page blocked or errored (%s): %s", status, url)
            return title, "", []

        discovered: list[tuple[str, str]] = []
        if url.rstrip("/") == "https://darglobal.co.uk/projects":
            links = await page.evaluate(
                """() => Array.from(document.querySelectorAll('a[href]'))
                .map(a => [a.innerText.replace(/\\s+/g,' ').trim().slice(0,90), a.href])"""
            )
            seen_u: set[str] = set()
            for txt, href in links:
                if not href.startswith("https://darglobal.co.uk/"):
                    continue
                path = urlparse(href).path.rstrip("/")
                if (
                    "/projects/" in path
                    and path.count("/") >= 2
                    and not path.endswith(("/villas", "/apartments", "/hotel-rooms", "/properties-in-uae", "/properties-in-saudi-arabia", "/properties-in-oman", "/properties-in-qatar", "/properties-in-spain", "/properties-in-uk"))
                    and href not in seen_u
                ):
                    seen_u.add(href)
                    discovered.append((txt, href))

        cleaned = _extract_clean_text(html, inner)
        return title, cleaned, discovered
    except Exception as exc:
        logger.warning("Failed scraping DarGlobal %s: %s", url, exc)
        return "", "", []
    finally:
        await page.close()


async def scrape_darglobal(context: BrowserContext) -> list[dict[str, Any]]:
    """Scrape public DarGlobal corporate, regional, partner, project, and press pages."""
    docs: list[dict[str, Any]] = []
    visited_urls: set[str] = set()
    discovered_projects: list[tuple[str, str]] = []

    targets = (
        DARGLOBAL_CORE_PAGES
        + DARGLOBAL_REGION_PAGES
        + DARGLOBAL_PARTNER_PAGES
        + DARGLOBAL_PRESS_PAGES
    )

    for item in targets:
        url = str(item["url"])
        visited_urls.add(url.rstrip("/"))
        logger.info("Scraping DarGlobal: %s", url)
        page_title, content, new_projects = await _scrape_single_page(context, url)
        if new_projects:
            discovered_projects.extend(new_projects)

        if len(content.strip()) < 100:
            logger.warning("Skipping low-content DarGlobal page: %s", url)
            continue

        tags = ["DarGlobal", str(item["category"])]
        if item.get("location"):
            tags.append(str(item["location"]))
        if item.get("brand"):
            tags.append(str(item["brand"]))

        docs.append(
            {
                "id": str(item["id"]),
                "source": "darglobal",
                "category": str(item["category"]),
                "title": str(item["title"]),
                "page_title": page_title,
                "url": url,
                "location": item.get("location"),
                "brand": item.get("brand"),
                "tags": tags,
                "content": content,
            }
        )

    # Also scrape up to 8 dynamically discovered individual project detail pages
    extra_count = 0
    for link_text, proj_url in discovered_projects:
        if extra_count >= 8:
            break
        norm = proj_url.rstrip("/")
        if norm in visited_urls:
            continue
        visited_urls.add(norm)
        logger.info("Scraping discovered DarGlobal project: %s", proj_url)
        page_title, content, _ = await _scrape_single_page(context, proj_url)
        if len(content.strip()) < 150:
            continue

        slug = urlparse(proj_url).path.strip("/").split("/")[-1]
        clean_title = page_title.split("|")[0].strip() if page_title else (link_text or slug.replace("-", " ").title())
        docs.append(
            {
                "id": f"dg-project-{slug[:40]}",
                "source": "darglobal",
                "category": "Luxury Project",
                "title": f"{clean_title} — DarGlobal",
                "page_title": page_title,
                "url": proj_url,
                "location": None,
                "brand": "DarGlobal",
                "tags": ["DarGlobal", "Luxury Project", clean_title],
                "content": content,
            }
        )
        extra_count += 1

    logger.info("Scraped %d DarGlobal documents.", len(docs))
    return docs
