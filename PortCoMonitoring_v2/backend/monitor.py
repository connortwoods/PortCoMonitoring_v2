"""
PortCoMonitoring backend entrypoint.

Runs on schedule or manual trigger (e.g. GitHub Actions):
  1. Pull company config from Supabase
  2. Scrape company websites, detect changes, upsert snapshots and change_log
  3. Fetch Glassdoor via Wayback (and SerpAPI fallback), compute deltas, detect review changes
  4. Optionally fetch LinkedIn headcount via SerpAPI
  5. Upsert glassdoor_insights and linkedin_snapshots
  6. Send one combined email alert if any changes detected
"""
import logging
import sys
from typing import Any

from config import require_supabase
from db import (
    get_companies,
    get_subscriber_emails,
    get_glassdoor_insight,
    upsert_glassdoor_insight,
    insert_change_log,
    get_change_log,
    upsert_linkedin_snapshot,
)
from website import fetch_and_detect_change
from glassdoor import fetch_glassdoor_insight
from linkedin import fetch_linkedin_headcount_serp
from alerts import build_combined_alert_html, send_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _company_glassdoor_url(company_row: dict[str, Any]) -> str | None:
    """Resolve Glassdoor URL: from companies.url where section is glassdoor, or from glassdoor_insights."""
    # If you store glassdoor URL in companies with section='glassdoor', use that
    if company_row.get("section") == "glassdoor" and company_row.get("url"):
        return company_row["url"]
    return None


def run_monitor(skip_linkedin: bool = False) -> list[dict[str, Any]]:
    """
    Run full monitoring pass. Returns list of change summaries for alerting.
    """
    require_supabase()
    companies = get_companies()
    if not companies:
        logger.info("No companies configured")
        return []

    # Group by company name for website URLs (blog, team, products) vs glassdoor
    by_company: dict[str, list[dict]] = {}
    glassdoor_url_by_company: dict[str, str] = {}
    for row in companies:
        name = row["company"]
        if name not in by_company:
            by_company[name] = []
        by_company[name].append(row)
        if row.get("section") == "glassdoor" and row.get("url"):
            glassdoor_url_by_company[name] = row["url"]

    changes: list[dict[str, Any]] = []

    # 1) Website change detection per URL (excluding glassdoor section for scraping)
    for name, rows in by_company.items():
        for r in rows:
            if (r.get("section") or "").lower() == "glassdoor":
                continue
            company_id = r["id"]
            url = r["url"]
            section = r.get("section") or "page"
            if fetch_and_detect_change(company_id, name, url, section):
                changes.append({"change_type": "website", "company": name, "section": section, "url": url})

    # 2) Glassdoor: fetch current + 12m, compare with previous, detect rating and review changes
    for name in by_company:
        glassdoor_url = glassdoor_url_by_company.get(name)
        insight = fetch_glassdoor_insight(name, glassdoor_url)
        if not insight.get("current_rating") and not insight.get("review_snippet"):
            continue
        prev = get_glassdoor_insight(name)
        rating_changed = False
        review_changed = False
        if prev is not None:
            if prev.get("current_rating") != insight.get("current_rating"):
                rating_changed = True
                insert_change_log(
                    name,
                    "glassdoor_rating",
                    previous_value=str(prev.get("current_rating")) if prev.get("current_rating") is not None else None,
                    new_value=str(insight.get("current_rating")) if insight.get("current_rating") is not None else None,
                    details={"rating_12m_ago": insight.get("rating_12m_ago"), "delta": insight.get("rating_delta")},
                )
            prev_snippet = (prev.get("review_snippet") or "").strip()
            new_snippet = (insight.get("review_snippet") or "").strip()
            if new_snippet and prev_snippet and new_snippet != prev_snippet:
                review_changed = True
                insert_change_log(
                    name,
                    "glassdoor_review",
                    previous_value=prev_snippet[:200] if prev_snippet else None,
                    new_value=new_snippet[:200] if new_snippet else None,
                )
        else:
            rating_changed = True  # first time we have data

        row = {
            "company": name,
            "glassdoor_url": glassdoor_url,
            "current_rating": insight.get("current_rating"),
            "rating_12m_ago": insight.get("rating_12m_ago"),
            "rating_delta": insight.get("rating_delta"),
            "review_snippet": insight.get("review_snippet"),
            "review_snippet_12m_ago": insight.get("review_snippet_12m_ago"),
            "source": insight.get("source"),
        }
        upsert_glassdoor_insight(row)
        if rating_changed or review_changed:
            changes.append({
                "change_type": "glassdoor",
                "company": name,
                "current_rating": insight.get("current_rating"),
                "delta": insight.get("rating_delta"),
                "review_changed": review_changed,
            })

    # 3) LinkedIn headcount (optional)
    if not skip_linkedin:
        for name in by_company:
            data = fetch_linkedin_headcount_serp(name)
            if data:
                upsert_linkedin_snapshot(
                    name,
                    data.get("headcount"),
                    data.get("employee_count_text"),
                    data.get("source"),
                )

    return changes


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="PortCoMonitoring backend run")
    p.add_argument("--skip-linkedin", action="store_true", help="Do not fetch LinkedIn headcount")
    p.add_argument("--no-email", action="store_true", help="Do not send alert email")
    args = p.parse_args()
    changes = run_monitor(skip_linkedin=args.skip_linkedin)
    logger.info("Run complete: %d changes", len(changes))
    if changes and not args.no_email:
        emails = get_subscriber_emails()
        if emails:
            html = build_combined_alert_html(changes)
            send_email(emails, "PortCo Monitoring — change alert", html)
        else:
            logger.info("No subscribers to email")
    elif not changes:
        logger.info("No changes; no alert sent.")


if __name__ == "__main__":
    main()
