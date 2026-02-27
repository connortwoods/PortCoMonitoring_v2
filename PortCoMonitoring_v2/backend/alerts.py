"""Email alerts with improved HTML formatting."""
import logging
from typing import Any

from config import (
    SENDGRID_API_KEY,
    ALERT_FROM_EMAIL,
    ALERT_FROM_NAME,
    SMTP_HOST,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_PORT,
)

logger = logging.getLogger(__name__)


def _html_header(title: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif; line-height: 1.5; color: #1a1a1a; max-width: 640px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 1.5rem; margin-bottom: 8px; color: #111; }}
    h2 {{ font-size: 1.15rem; margin-top: 20px; margin-bottom: 8px; color: #333; }}
    .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 20px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
    th, td {{ border: 1px solid #e0e0e0; padding: 10px 12px; text-align: left; }}
    th {{ background: #f5f5f5; font-weight: 600; }}
    .delta-positive {{ color: #0d7d0d; }}
    .delta-negative {{ color: #b91c1c; }}
    .delta-neutral {{ color: #666; }}
    .footer {{ margin-top: 28px; font-size: 0.85rem; color: #888; }}
    ul {{ margin: 8px 0; padding-left: 20px; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p class="meta">PortCo Monitoring — automated change alert</p>
"""


def _html_footer() -> str:
    return """
  <p class="footer">You received this because you are subscribed to PortCo Monitoring. Manage preferences in the dashboard.</p>
</body>
</html>
"""


def build_website_change_html(company: str, section: str, url: str) -> str:
    """Single website change."""
    body = f"""
  <h2>Website update</h2>
  <p><strong>{company}</strong> — section <strong>{section}</strong> has changed.</p>
  <p><a href="{url}">View page</a></p>
"""
    return _html_header("Portfolio company website change") + body + _html_footer()


def build_glassdoor_change_html(company: str, current_rating: float | None, rating_12m: float | None, delta: float | None, snippet: str | None, review_changed: bool = False) -> str:
    """Glassdoor rating (and optional review) change."""
    delta_class = "delta-neutral"
    if delta is not None:
        if delta > 0:
            delta_class = "delta-positive"
        elif delta < 0:
            delta_class = "delta-negative"
    delta_str = f"<span class=\"{delta_class}\">{delta:+.2f}</span>" if delta is not None else "—"
    rows = [
        ("Company", company),
        ("Current rating", str(current_rating) if current_rating is not None else "—"),
        ("12 months ago", str(rating_12m) if rating_12m is not None else "—"),
        ("Change", delta_str),
    ]
    table_cells = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
    body = f"""
  <h2>Glassdoor update</h2>
  <table>
    {table_cells}
  </table>
"""
    if review_changed and snippet:
        body += f"  <p><strong>Recent snippet:</strong> {snippet}</p>\n"
    elif snippet:
        body += f"  <p><strong>Sample review:</strong> {snippet}</p>\n"
    return _html_header("Portfolio company Glassdoor update") + body + _html_footer()


def build_combined_alert_html(changes: list[dict[str, Any]]) -> str:
    """Multiple changes in one email."""
    parts = []
    for c in changes:
        kind = c.get("change_type", "")
        if kind == "website":
            parts.append(f"<li><strong>{c.get('company', '')}</strong> — {c.get('section', '')} page changed. <a href=\"{c.get('url', '#')}\">View</a></li>")
        elif kind == "glassdoor":
            d = c.get("delta")
            d_str = f" ({d:+.2f})" if d is not None else ""
            parts.append(f"<li><strong>{c.get('company', '')}</strong> — Glassdoor rating: {c.get('current_rating', '—')}{d_str}</li>")
    list_html = "<ul>" + "".join(parts) + "</ul>" if parts else "<p>No details.</p>"
    body = "  <h2>Summary</h2>\n  " + list_html + "\n"
    return _html_header("PortCo Monitoring — change alert") + body + _html_footer()


def send_email(to_emails: list[str], subject: str, html_body: str) -> bool:
    """Send via SendGrid or SMTP. Returns True on success."""
    if not to_emails:
        return True
    if SENDGRID_API_KEY:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            message = Mail(
                from_email=(ALERT_FROM_EMAIL or "noreply@portcomonitoring.local", ALERT_FROM_NAME),
                to_emails=to_emails,
                subject=subject,
                html_content=html_body,
            )
            SendGridAPIClient(SENDGRID_API_KEY).send(message)
            return True
        except Exception as e:
            logger.error("SendGrid send failed: %s", e)
            return False
    if SMTP_HOST and SMTP_USER and SMTP_PASSWORD:
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{ALERT_FROM_NAME} <{ALERT_FROM_EMAIL or SMTP_USER}>"
            msg["To"] = ", ".join(to_emails)
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASSWORD)
                s.sendmail(msg["From"], to_emails, msg.as_string())
            return True
        except Exception as e:
            logger.error("SMTP send failed: %s", e)
            return False
    logger.warning("No email backend configured (SendGrid or SMTP)")
    return False
