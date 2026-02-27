"""Load config from environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root or backend/
for d in [Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent]:
    env_file = d / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        break

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "").strip()
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "").strip()
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "").strip()
ALERT_FROM_EMAIL = os.environ.get("ALERT_FROM_EMAIL", "").strip()
ALERT_FROM_NAME = os.environ.get("ALERT_FROM_NAME", "PortCo Monitoring")

# SMTP fallback
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()

def require_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY) must be set")
