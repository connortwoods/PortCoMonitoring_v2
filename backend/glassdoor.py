"""
Glassdoor data via Wayback Machine (primary) and SerpAPI (fallback).
No direct live scraping of Glassdoor (Cloudflare blocks).
"""
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Any
import httpx

from config import SERPAPI_KEY

logger = logging.getLogger(__name__)

WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx"
WAYBACK_RAW = "https://web.archive.org/web/{timestamp}id_/{url}"

# Multiple patterns for rating (e.g. "4.2", "4,2", "4.2 out of 5", "Rating: 4.2")
RATING_PATTERNS = [
    r"(\d{1}\.\d{1,2})\s*out\s*of\s*5",
    r"rating[:\s]+(\d{1}\.\d{1,2})",
    r"(\d{1}\.\d{1,2})\s*/\s*5",
    r'"rating"\s*:\s*(\d{1}\.\d{1,2})',
    r'data-rating="(\d{1}\.\d{1,2})"',
    r'ratingValue["\s:]+(\d{1}\.\d{1,2})',
    r"\b(\d{1}\.\d{1,2})\s*stars?",
    r"\b(\d{1}\.\d{1,2})\b(?=.*glassdoor|.*review)",
]
RATING_FALLBACK = re.compile(r"\b(\d{1}\.\d{1,2})\b")

# Snippet: first meaningful review-like text (avoid nav/footer)
SNIPPET_PATTERNS = [
    r'(?:review|pros?|cons?|advice)[^>]*>([^<]{20,200})',
    r'"(?:reviewBody|reviewSnippet|description)"\s*:\s*"([^"]{20,200})',
    r'<p[^>]*class="[^"]*review[^"]*"[^>]*>([^<]{20,300})',
]


def _parse_rating_from_html(html: str) -> float | None:
    """Extract a single numeric rating from HTML; prefer structured then heuristic."""
    if not html:
        return None
    html_lower = html.lower()
    for pattern in RATING_PATTERNS:
        m = re.search(pattern, html_lower, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                v = float(m.group(1).replace(",", "."))
                if 1 <= v <= 5:
                    return round(v, 2)
            except (ValueError, IndexError):
                continue
    # Last resort: any X.X in plausible range
    for m in RATING_FALLBACK.finditer(html):
        try:
            v = float(m.group(1).replace(",", "."))
            if 1 <= v <= 5:
                return round(v, 2)
        except ValueError:
            continue
    return None


def _parse_snippet_from_html(html: str, max_len: int = 200) -> str | None:
    """Extract one short review snippet from HTML."""
    if not html:
        return None
    for pattern in SNIPPET_PATTERNS:
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if m:
            raw = m.group(1).strip()
            raw = re.sub(r"\s+", " ", raw).strip()
            if len(raw) >= 20:
                return (raw[:max_len] + "…") if len(raw) > max_len else raw
    return None


def _wayback_timestamps_for_url(url: str, limit: int = 20) -> list[str]:
    """Return list of available snapshot timestamps (newest first) for url."""
    try:
        resp = httpx.get(
            WAYBACK_CDX,
            params={"url": url, "output": "json", "limit": limit, "collapse": "timestamp:8"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data or len(data) < 2:
            return []
        # First row is header; column 1 is timestamp
        ts_col = None
        for i, h in enumerate(data[0]):
            if h == "timestamp":
                ts_col = i
                break
        if ts_col is None:
            ts_col = 1
        return [row[ts_col] for row in data[1:] if len(row) > ts_col]
    except Exception as e:
        logger.warning("Wayback CDX failed for %s: %s", url, e)
        return []


def _fetch_wayback_page(url: str, timestamp: str) -> str | None:
    """Fetch archived page body from Wayback. url should be plain (no wayback prefix)."""
    # id_ keeps the page as-is (no redirect)
    wayback_url = WAYBACK_RAW.format(timestamp=timestamp, url=url)
    try:
        r = httpx.get(wayback_url, follow_redirects=True, timeout=25)
        r.raise_for_status()
        return r.text
    except Exception as e:
        logger.warning("Wayback fetch failed %s @ %s: %s", url, timestamp, e)
        return None


def get_wayback_rating_and_snippet(glassdoor_url: str, when: datetime | None = None) -> tuple[float | None, str | None]:
    """
    Get rating and snippet from Wayback for a given time.
    If when is None, use most recent snapshot.
    Returns (rating, snippet).
    """
    timestamps = _wayback_timestamps_for_url(glassdoor_url, limit=50)
    if not timestamps:
        return None, None

    if when is not None:
        target = when.strftime("%Y%m%d")
        # Pick closest timestamp on or before target
        chosen = None
        for ts in timestamps:
            if ts <= target:
                chosen = ts
                break
        if chosen is None:
            chosen = timestamps[-1]
    else:
        chosen = timestamps[0]

    html = _fetch_wayback_page(glassdoor_url, chosen)
    if not html:
        return None, None
    rating = _parse_rating_from_html(html)
    snippet = _parse_snippet_from_html(html)
    return rating, snippet


def get_glassdoor_via_wayback(glassdoor_url: str) -> dict[str, Any]:
    """
    Fetch current and ~12 months ago from Wayback.
    Returns dict: current_rating, rating_12m_ago, review_snippet, review_snippet_12m_ago, source.
    """
    now = datetime.now(timezone.utc)
    twelve_months_ago = now - timedelta(days=365)

    current_rating, current_snippet = get_wayback_rating_and_snippet(glassdoor_url, when=now)
    rating_12m, snippet_12m = get_wayback_rating_and_snippet(glassdoor_url, when=twelve_months_ago)

    delta = None
    if current_rating is not None and rating_12m is not None:
        delta = round(current_rating - rating_12m, 2)

    return {
        "current_rating": current_rating,
        "rating_12m_ago": rating_12m,
        "rating_delta": delta,
        "review_snippet": current_snippet,
        "review_snippet_12m_ago": snippet_12m,
        "source": "wayback",
    }


def get_glassdoor_via_serpapi(company_name: str, glassdoor_url: str | None = None) -> dict[str, Any] | None:
    """
    Fallback: SerpAPI Google search for "company name glassdoor rating".
    Returns same shape as get_glassdoor_via_wayback or None if no key / no data.
    """
    if not SERPAPI_KEY:
        return None
    query = f"{company_name} glassdoor rating reviews"
    try:
        r = httpx.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": SERPAPI_KEY, "num": 5},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("SerpAPI request failed: %s", e)
        return None

    # SerpAPI may return knowledge panel or organic snippets with rating
    rating = None
    snippet = None
    organic = data.get("organic_results") or []
    for item in organic:
        snippet_text = (item.get("snippet") or "") + " " + (item.get("title") or "")
        parsed = _parse_rating_from_html(snippet_text)
        if parsed is not None:
            rating = parsed
            snippet = (item.get("snippet") or "")[:200]
            break

    if rating is None:
        return None
    return {
        "current_rating": rating,
        "rating_12m_ago": None,
        "rating_delta": None,
        "review_snippet": snippet,
        "review_snippet_12m_ago": None,
        "source": "serpapi",
    }


def fetch_glassdoor_insight(company_name: str, glassdoor_url: str | None) -> dict[str, Any]:
    """
    Primary: Wayback. Fallback: SerpAPI if Wayback has no recent rating.
    Merges into one result dict; caller can add company, glassdoor_url, etc.
    """
    result = {
        "current_rating": None,
        "rating_12m_ago": None,
        "rating_delta": None,
        "review_snippet": None,
        "review_snippet_12m_ago": None,
        "source": None,
    }
    if glassdoor_url:
        wayback_result = get_glassdoor_via_wayback(glassdoor_url)
        if wayback_result.get("current_rating") is not None:
            result.update(wayback_result)
    if result.get("current_rating") is None and company_name:
        serp = get_glassdoor_via_serpapi(company_name, glassdoor_url)
        if serp:
            result.update(serp)
    return result
