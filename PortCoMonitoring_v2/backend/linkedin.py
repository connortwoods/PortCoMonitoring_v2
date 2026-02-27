"""
LinkedIn headcount / hiring signals.

Data quality note: LinkedIn blocks automated scraping (Cloudflare, login walls).
Options that work in practice:
  1. SerpAPI "LinkedIn company" or "site:linkedin.com/company <name>" for snippet text (e.g. "X employees").
  2. Manual CSV upload of headcount in the frontend, stored in Supabase.
  3. Third-party APIs (e.g. Apollo, Clearbit) if you have a contract.

This module provides SerpAPI-based extraction when SERPAPI_KEY is set; otherwise no-op.
Schema: add optional table linkedin_snapshots(company, headcount, employee_count_text, fetched_at) if you want to store it.
"""

import re
import logging
from typing import Any

import httpx

from config import SERPAPI_KEY

logger = logging.getLogger(__name__)

# Match "500-1000 employees", "5,000 employees", "10k employees", "500+"
HEADCOUNT_PATTERNS = [
    r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?k?)\s*[-–]\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?k?)\s*employees?",
    r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?k?)\s*\+?\s*employees?",
    r"(\d{1,3}(?:,\d{3})*)\s*employees?",
]


def _parse_headcount(text: str) -> int | None:
    """Parse a single number from employee count text; for ranges use the first number."""
    if not text:
        return None
    text = text.replace(",", "").replace(" ", "")
    for pattern in HEADCOUNT_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1).lower().replace("k", "000").replace(".", "")
            try:
                return int(float(raw))
            except ValueError:
                continue
    return None


def fetch_linkedin_headcount_serp(company_name: str) -> dict[str, Any] | None:
    """
    Use SerpAPI to search "company name LinkedIn" and parse employee count from snippets.
    Returns dict with headcount (int or None), employee_count_text (str), source.
    """
    if not SERPAPI_KEY:
        return None
    query = f"{company_name} LinkedIn company employees"
    try:
        r = httpx.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": SERPAPI_KEY, "num": 10},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("SerpAPI LinkedIn search failed: %s", e)
        return None

    organic = data.get("organic_results") or []
    for item in organic:
        snippet = (item.get("snippet") or "") + " " + (item.get("title") or "")
        count = _parse_headcount(snippet)
        if count is not None:
            return {
                "headcount": count,
                "employee_count_text": snippet.strip()[:200],
                "source": "serpapi",
            }
    return None
