"""Website change detection: fetch URL, hash content, compare with last snapshot."""
import hashlib
import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup

from db import get_snapshot, upsert_snapshot, insert_change_log

logger = logging.getLogger(__name__)


def _normalize_html(html: str) -> str:
    """Reduce noise for hashing: strip script/style, normalize whitespace."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return " ".join(text.split())


def content_hash(html: str) -> str:
    """SHA256 of normalized body."""
    return hashlib.sha256(_normalize_html(html).encode("utf-8")).hexdigest()


def fetch_and_detect_change(company_id: str, company_name: str, url: str, section: str) -> bool:
    """
    Fetch URL, compute hash, compare with last snapshot. If changed, upsert snapshot and log.
    Returns True if a change was detected.
    """
    try:
        r = httpx.get(url, follow_redirects=True, timeout=30)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        logger.warning("Fetch failed %s %s: %s", company_name, url, e)
        return False

    new_hash = content_hash(html)
    prev = get_snapshot(company_id)
    if prev and prev.get("content_hash") == new_hash:
        return False

    if prev:
        insert_change_log(
            company_name,
            "website",
            previous_value=prev.get("content_hash"),
            new_value=new_hash,
            details={"section": section, "url": url},
        )
    upsert_snapshot(company_id, new_hash)
    return True
