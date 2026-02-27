# PortCoMonitoring

Automated portfolio company monitoring: tracks company websites (blog, team, products) and Glassdoor, stores structured data in Supabase, and sends email alerts when meaningful changes occur.

## Architecture

| Component | Stack | Role |
|-----------|--------|------|
| **Frontend** | Streamlit (Streamlit Cloud) | Manage company URLs & subscribers, Glassdoor dashboard, "Run Now" trigger. Read-only from Supabase. |
| **Backend** | GitHub Actions + `monitor.py` | Scheduled or manual run: scrape sites, Glassdoor via Wayback/SerpAPI, upsert Supabase, send alerts. |
| **Data** | Supabase | `companies`, `subscribers`, `snapshots`, `glassdoor_insights`, `change_log`. RLS for anon inserts/updates. |

## Data sources

- **Company websites**: Direct scraping for blog/team/products sections.
- **Glassdoor**: No live scraping (Cloudflare). Uses [Wayback Machine](https://web.archive.org/) (current + 12 months ago) with [SerpAPI](https://serpapi.com/) fallback for ratings and review snippets.
- **LinkedIn** (optional): Headcount/hiring via public company page or SerpAPI where available; see notes in code for limitations.

## Setup

### 1. Supabase

1. Create a project at [supabase.com](https://supabase.com).
2. Run migrations in `supabase/migrations/` (or apply `001_initial.sql` in SQL Editor).
3. Enable RLS; policies allow `anon` for inserts/updates (for GitHub Actions).
4. Copy Project URL and `service_role` or `anon` key.

### 2. Environment

- **Backend (GitHub Actions)**  
  Set repo secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (or anon key if RLS allows), `SERPAPI_KEY` (optional), `ALERT_FROM_EMAIL`, `SENDGRID_API_KEY` (or your SMTP vars).
- **Frontend (Streamlit Cloud)**  
  Set secrets: `SUPABASE_URL`, `SUPABASE_ANON_KEY` (read-only is enough if you use anon + RLS).
- **Local**  
  Copy `.env.example` to `.env` and fill in values.

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
python monitor.py   # optional: run locally
```

### 4. Frontend

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

### 5. GitHub Actions

- Workflow: `.github/workflows/monitor.yml` (scheduled + `workflow_dispatch`).
- Ensure secrets above are set; workflow uses `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` (or anon) and optional `SERPAPI_KEY`, email keys.

## Project layout

```
PortCoMonitoring/
├── backend/
│   ├── monitor.py          # Entrypoint: config → scrape → Glassdoor → upsert → alerts
│   ├── config.py           # Env and options
│   ├── db.py               # Supabase client
│   ├── glassdoor.py        # Wayback + SerpAPI, rating/review parsing
│   ├── website.py          # Company site change detection
│   ├── linkedin.py         # LinkedIn headcount (when available)
│   ├── alerts.py           # Email (HTML) alerts
│   └── requirements.txt
├── frontend/
│   ├── app.py              # Streamlit: dashboard, companies, subscribers, Run Now
│   └── requirements.txt
├── supabase/
│   └── migrations/
│       └── 001_initial.sql
├── .github/workflows/
│   └── monitor.yml
├── .env.example
└── README.md
```

## Priorities (current)

- Robust Glassdoor rating/review parsing and review change detection
- LinkedIn headcount integration (with fallbacks)
- Historical change log and better HTML email formatting
- Reliability: Wayback-first, SerpAPI fallback, no direct Glassdoor scraping
