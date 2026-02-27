"""Supabase client and helpers for PortCoMonitoring."""
from __future__ import annotations

from typing import Any

from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY, require_supabase

_client: Client | None = None


def get_client() -> Client:
    require_supabase()
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def get_companies() -> list[dict[str, Any]]:
    """Fetch all companies with section and URL."""
    r = get_client().table("companies").select("id, company, section, url").execute()
    if r.data is None:
        return []
    return list(r.data)


def get_subscriber_emails() -> list[str]:
    """Fetch all subscriber emails."""
    r = get_client().table("subscribers").select("email").execute()
    if not r.data:
        return []
    return [row["email"] for row in r.data if row.get("email")]


def get_snapshot(company_id: str) -> dict[str, Any] | None:
    """Get latest snapshot for a company (by company_id)."""
    r = (
        get_client()
        .table("snapshots")
        .select("id, content_hash, fetched_at")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        return None
    return r.data[0]


def upsert_snapshot(company_id: str, content_hash: str) -> None:
    """Insert or update snapshot for company_id (one row per company)."""
    get_client().table("snapshots").upsert(
        {"company_id": company_id, "content_hash": content_hash},
        on_conflict="company_id",
    ).execute()


def get_glassdoor_insight(company: str) -> dict[str, Any] | None:
    """Get current Glassdoor insight row for company."""
    r = (
        get_client()
        .table("glassdoor_insights")
        .select("*")
        .eq("company", company)
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        return None
    return r.data[0]


def upsert_glassdoor_insight(row: dict[str, Any]) -> None:
    """Upsert glassdoor_insights by company."""
    get_client().table("glassdoor_insights").upsert(row, on_conflict="company").execute()


def insert_change_log(company: str, change_type: str, previous_value: str | None = None, new_value: str | None = None, details: dict | None = None) -> None:
    """Append to change_log."""
    payload = {
        "company": company,
        "change_type": change_type,
        "previous_value": previous_value,
        "new_value": new_value,
        "details": details or {},
    }
    get_client().table("change_log").insert(payload).execute()


def get_change_log(company: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Fetch recent change_log rows, optionally filtered by company."""
    q = get_client().table("change_log").select("*").order("created_at", desc=True).limit(limit)
    if company:
        q = q.eq("company", company)
    r = q.execute()
    return list(r.data or [])


def upsert_linkedin_snapshot(company: str, headcount: int | None, employee_count_text: str | None, source: str | None) -> None:
    """Upsert linkedin_snapshots by company."""
    get_client().table("linkedin_snapshots").upsert(
        {
            "company": company,
            "headcount": headcount,
            "employee_count_text": employee_count_text,
            "source": source or "serpapi",
        },
        on_conflict="company",
    ).execute()
