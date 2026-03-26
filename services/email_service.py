"""
services/email_service.py
IMAP email monitoring — fetches unseen emails whose subject matches the filter,
downloads attachments, and yields metadata for further processing.
"""
import email
import imaplib
import os
from email.header import decode_header
from pathlib import Path
from typing import Generator

from config.settings import ALLOWED_EXTENSIONS, DOWNLOAD_DIR, EMAIL_CONFIG
from utils.file_helpers import compute_bytes_hash, ensure_dir, safe_filename
from utils.logger import get_logger

logger = get_logger("email_service")


# ── helpers ────────────────────────────────────────────────────────────────────

def _decode_str(value: str | bytes | None, charset: str | None = None) -> str:
    """Decode an RFC-2047-encoded header fragment."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(charset or "utf-8", errors="replace")
    return value


def _parse_subject(raw_subject: str) -> str:
    parts = decode_header(raw_subject)
    return "".join(_decode_str(text, enc) for text, enc in parts)


# ── main class ─────────────────────────────────────────────────────────────────

class EmailService:
    """Wraps an IMAP connection and yields attachment file paths."""

    def __init__(self) -> None:
        self.cfg = EMAIL_CONFIG
        self._seen_hashes: set[str] = set()   # in-memory dedup across polls
        ensure_dir(DOWNLOAD_DIR)

    # ── connection ──────────────────────────────────────────────────────────────

    def _connect(self) -> imaplib.IMAP4_SSL:
        logger.info("Connecting to IMAP %s:%s …", self.cfg["imap_host"], self.cfg["imap_port"])
        conn = imaplib.IMAP4_SSL(self.cfg["imap_host"], self.cfg["imap_port"])
        conn.login(self.cfg["address"], self.cfg["password"])
        conn.select("INBOX")
        logger.info("IMAP login successful.")
        return conn

    # ── fetch ───────────────────────────────────────────────────────────────────

    def fetch_invoice_attachments(self) -> Generator[dict, None, None]:
        """
        Connects to IMAP, searches UNSEEN emails whose subject contains the
        configured filter, and yields dicts:
            {
                "email_uid":   bytes,
                "from_address": str,
                "subject":     str,
                "filepath":    str,
                "filename":    str,
            }
        Marks processed emails as SEEN.
        """
        try:
            conn = self._connect()
        except Exception as exc:
            logger.error("IMAP connection failed: %s", exc)
            return

        try:
            subject_bytes = self.cfg["subject_filter"].encode()
            status, data = conn.uid("SEARCH", None, b'UNSEEN SUBJECT "' + subject_bytes + b'"')
            if status != "OK":
                logger.warning("IMAP SEARCH returned status: %s", status)
                return

            uids = data[0].split()
            logger.info("Found %d matching unseen email(s).", len(uids))

            for uid in uids:
                try:
                    yield from self._process_email(conn, uid)
                    # Mark as seen after successful processing
                    conn.uid("STORE", uid, "+FLAGS", "\\Seen")
                except Exception as exc:
                    logger.error("Error processing email UID %s: %s", uid, exc)

        finally:
            try:
                conn.close()
                conn.logout()
            except Exception:
                pass

    # ── per-email processing ────────────────────────────────────────────────────

    def _process_email(self, conn: imaplib.IMAP4_SSL, uid: bytes) -> Generator[dict, None, None]:
        status, msg_data = conn.uid("FETCH", uid, "(RFC822)")
        if status != "OK" or not msg_data or msg_data[0] is None:
            logger.warning("Could not fetch email UID %s.", uid)
            return

        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        subject     = _parse_subject(msg.get("Subject", ""))
        from_header = msg.get("From", "")
        logger.info("Processing email | Subject: %s | From: %s", subject, from_header)

        for part in msg.walk():
            content_disp = part.get_content_disposition() or ""
            if "attachment" not in content_disp.lower():
                continue

            raw_name = part.get_filename() or "attachment"
            filename = safe_filename(_parse_subject(raw_name))
            ext      = Path(filename).suffix.lower()

            if ext not in ALLOWED_EXTENSIONS:
                logger.debug("Skipping unsupported attachment: %s", filename)
                continue

            payload = part.get_payload(decode=True)
            if not payload:
                continue

            file_hash = compute_bytes_hash(payload)
            if file_hash in self._seen_hashes:
                logger.info("Duplicate attachment skipped (hash match): %s", filename)
                continue

            # Save
            dest_path = os.path.join(DOWNLOAD_DIR, f"{file_hash[:8]}_{filename}")
            with open(dest_path, "wb") as f:
                f.write(payload)

            self._seen_hashes.add(file_hash)
            logger.info("Saved attachment: %s", dest_path)

            yield {
                "email_uid":    uid.decode(),
                "from_address": from_header,
                "subject":      subject,
                "filepath":     dest_path,
                "filename":     filename,
            }
