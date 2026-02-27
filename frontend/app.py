"""
PortCoMonitoring Streamlit frontend.

- Manage company URLs (and optional Glassdoor URL per company)
- Manage subscriber emails
- Dashboard: Glassdoor insights + optional change log
- Run Now: trigger backend via GitHub Actions workflow_dispatch (link or instructions)
"""
import os
from pathlib import Path

import streamlit as st
import pandas as pd

# Load .env from project root or frontend/
for d in [Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent]:
    env_file = d / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
        break

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "").strip()


def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Set SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_SERVICE_KEY) in secrets/env.")
        return None
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


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
        st.markdown("""
        The backend runs on **GitHub Actions** (scheduled or manual).

        To trigger a run **now**:
        1. Open your repo → **Actions** → **PortCo Monitor**.
        2. Click **Run workflow** → **Run workflow**.

        Ensure these repo secrets are set: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and optionally  
        `SERPAPI_KEY`, `SENDGRID_API_KEY`, `ALERT_FROM_EMAIL`.
        """)
        st.link_button("Open GitHub Actions", "https://github.com/YOUR_USERNAME/PortCoMonitoring/actions", type="secondary")


if __name__ == "__main__":
    main()
