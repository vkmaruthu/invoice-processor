"""
config/settings.py
Central configuration — reads from environment variables or .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Email ──────────────────────────────────────────────────────────────────────
EMAIL_CONFIG = {
    "address":  os.getenv("EMAIL_ADDRESS", "your@gmail.com"),
    "password": os.getenv("EMAIL_PASSWORD", "your_app_password"),   # Gmail App Password
    "imap_host": os.getenv("IMAP_HOST", "imap.gmail.com"),
    "imap_port": int(os.getenv("IMAP_PORT", 993)),
    "subject_filter": os.getenv("SUBJECT_FILTER", "Invoice Copy"),
    "poll_interval_seconds": int(os.getenv("POLL_INTERVAL", 30)),
}

# ── MongoDB ────────────────────────────────────────────────────────────────────
MONGO_CONFIG = {
    "uri":        os.getenv("MONGO_URI", "mongodb://localhost:27017"),
    "db_name":    os.getenv("MONGO_DB",  "invoice_db"),
    "collection": os.getenv("MONGO_COLLECTION", "invoices"),
}

# ── Google Gemini ──────────────────────────────────────────────────────────────
GEMINI_CONFIG = {
    "api_key": os.getenv("GEMINI_API_KEY"),
    "model":   os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
}

# ── Local paths ────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOAD_DIR  = os.path.join(BASE_DIR, "downloads")
LOG_DIR       = os.path.join(BASE_DIR, "logs")

# ── Allowed attachment types ───────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
