"""
PortCoMonitoring Streamlit frontend.

- Manage company URLs (and optional Glassdoor URL per company)
- Manage subscriber emails
- Dashboard: Glassdoor insights + optional change log
- Run Now: trigger backend via GitHub Actions workflow_dispatch (link or instructions)
"""
import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# Load .env from project root or frontend/
for d in [Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent]:
    env_file = d / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
        break

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

# GitHub Actions trigger configuration (for "Run now" button)
GITHUB_REPO = os.environ.get("GITHUB_REPO", "").strip()  # e.g. "your-username/PortCoMonitoring_v2"
GITHUB_WORKFLOW_ID = os.environ.get("GITHUB_WORKFLOW_ID", "monitor.yml").strip()
GITHUB_WORKFLOW_TOKEN = os.environ.get("GITHUB_WORKFLOW_TOKEN", "").strip()
GITHUB_DEFAULT_REF = os.environ.get("GITHUB_DEFAULT_REF", "main").strip()


def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Set SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_SERVICE_KEY) in secrets/env.")
        return None
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def trigger_github_workflow() -> None:
    """
    Trigger the GitHub Actions workflow that runs the backend monitor via workflow_dispatch.
    Requires Streamlit secrets/env:
      - GITHUB_REPO (e.g. "your-username/PortCoMonitoring_v2")
      - GITHUB_WORKFLOW_TOKEN (PAT with repo + workflow scope)
      - optional: GITHUB_WORKFLOW_ID (defaults to "monitor.yml"), GITHUB_DEFAULT_REF (defaults to "main")
    """
    if not GITHUB_REPO or not GITHUB_WORKFLOW_TOKEN:
        st.error(
            "GitHub workflow trigger is not configured. "
            "Set GITHUB_REPO and GITHUB_WORKFLOW_TOKEN in Streamlit secrets."
        )
        return

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW_ID}/dispatches"
    headers = {
        "Authorization": f"Bearer {GITHUB_WORKFLOW_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    payload = {"ref": GITHUB_DEFAULT_REF}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code in (201, 204):
            st.success("Backend run triggered. Check GitHub Actions for progress.")
        else:
            st.error(f"Failed to trigger workflow ({resp.status_code}): {resp.text[:300]}")
    except Exception as exc:
        st.error(f"Error triggering GitHub workflow: {exc}")


def main():
    st.set_page_config(page_title="PortCo Monitoring", page_icon="📊", layout="wide")
    st.title("PortCo Monitoring")
    st.caption("Portfolio company monitoring — websites & Glassdoor. Data is read from Supabase.")

    sb = get_supabase()
    if sb is None:
        return

    tab_dash, tab_companies, tab_subscribers, tab_log, tab_run = st.tabs([
        "Dashboard", "Companies & URLs", "Subscribers", "Change log", "Run now",
    ])

    with tab_dash:
        r = sb.table("glassdoor_insights").select("*").order("updated_at", desc=True).execute()
        rows = r.data or []
        if not rows:
            st.info("No Glassdoor insights yet. Add companies with a Glassdoor URL and run the backend.")
        else:
            df = pd.DataFrame(rows)
            cols = ["company", "current_rating", "rating_12m_ago", "rating_delta", "source", "updated_at"]
            display_df = df[[c for c in cols if c in df.columns]]
            st.dataframe(display_df, use_container_width=True)
            if "review_snippet" in df.columns:
                with st.expander("Review snippets"):
                    for _, row in df.iterrows():
                        if pd.notna(row.get("review_snippet")) and str(row.get("review_snippet")).strip():
                            st.markdown(f"**{row.get('company', '')}** — {row.get('review_snippet', '')[:200]}")

    with tab_companies:
        r = sb.table("companies").select("id, company, section, url").order("company").execute()
        companies = r.data or []
        if companies:
            st.dataframe(pd.DataFrame(companies), use_container_width=True)
        st.subheader("Add company URL")
        with st.form("add_company"):
            company = st.text_input("Company name")
            section = st.selectbox("Section", ["blog", "team", "products", "glassdoor", "other"])
            url = st.text_input("URL")
            if st.form_submit_button("Add"):
                if company and url:
                    try:
                        sb.table("companies").upsert(
                            {"company": company, "section": section, "url": url},
                            on_conflict="company,section",
                        ).execute()
                        st.success("Added. Refresh to see.")
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.warning("Company and URL required.")

    with tab_subscribers:
        r = sb.table("subscribers").select("email, created_at").execute()
        subs = r.data or []
        if subs:
            st.dataframe(pd.DataFrame(subs), use_container_width=True)
        st.subheader("Add subscriber")
        with st.form("add_sub"):
            email = st.text_input("Email")
            if st.form_submit_button("Add"):
                if email and "@" in email:
                    try:
                        sb.table("subscribers").insert({"email": email}).execute()
                        st.success("Added.")
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.warning("Valid email required.")

    with tab_log:
        company_filter = st.text_input("Filter by company (optional)")
        r = sb.table("change_log").select("*").order("created_at", desc=True).limit(100).execute()
        log_rows = r.data or []
        if company_filter:
            log_rows = [x for x in log_rows if (x.get("company") or "").lower() == company_filter.lower()]
        if not log_rows:
            st.info("No change log entries yet.")
        else:
            st.dataframe(pd.DataFrame(log_rows), use_container_width=True)

    with tab_run:
        st.markdown(
            """
            The backend runs on **GitHub Actions** (scheduled daily and manual).

            - It runs `backend/monitor.py`, which:
              - Scrapes company websites and detects changes
              - Updates Glassdoor insights
              - Updates LinkedIn headcount (when configured)
            """
        )

        if GITHUB_REPO:
            repo_url = f"https://github.com/{GITHUB_REPO}"
            actions_url = f"{repo_url}/actions"
        else:
            repo_url = "https://github.com"
            actions_url = "https://github.com"

        st.link_button("Open GitHub Actions", actions_url, type="secondary")

        st.divider()
        st.subheader("Run now from Streamlit")
        st.caption(
            "This triggers the GitHub Actions workflow (`monitor.yml`) via the GitHub API. "
            "Configure `GITHUB_REPO` and `GITHUB_WORKFLOW_TOKEN` in Streamlit secrets."
        )

        if st.button("Run backend now", type="primary"):
            trigger_github_workflow()


if __name__ == "__main__":
    main()
