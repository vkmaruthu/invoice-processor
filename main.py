"""
main.py  ←  ENTRY POINT
Run:  python main.py

The scheduler polls for new invoice emails every EMAIL_CONFIG["poll_interval_seconds"]
seconds (default 30). Ctrl-C to stop cleanly.
"""
import signal
import sys
import time

import schedule

from config.settings import EMAIL_CONFIG
from controllers.invoice_controller import InvoiceController
from utils.logger import get_logger

logger = get_logger("main")

# Global controller reference (needed for graceful shutdown)
_controller: InvoiceController | None = None


# ── graceful shutdown ──────────────────────────────────────────────────────────

def _handle_signal(sig, frame):
    logger.info("Shutdown signal received — stopping …")
    if _controller:
        _controller.shutdown()
    sys.exit(0)

signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ── scheduled job ──────────────────────────────────────────────────────────────

def poll_job() -> None:
    logger.info("═══ Polling for new invoice emails … ═══")
    try:
        _controller.run_pipeline()
    except Exception as exc:
        logger.error("Unhandled error in poll_job: %s", exc, exc_info=True)


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    global _controller

    logger.info("╔══════════════════════════════════════════╗") 
    logger.info("║   Invoice Processor  —  starting up …    ║")
    logger.info("╚══════════════════════════════════════════╝")

    _controller = InvoiceController()

    interval = EMAIL_CONFIG["poll_interval_seconds"]
    schedule.every(interval).seconds.do(poll_job)
    logger.info("Scheduler set: polling every %d seconds.", interval)

    # Run immediately on start, then on schedule
    poll_job()

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
