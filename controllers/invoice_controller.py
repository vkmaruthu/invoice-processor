"""
controllers/invoice_controller.py
Orchestrates the end-to-end pipeline for a single attachment:
  EmailService → OCRService → GeminiService → DatabaseService
"""
from services.database_service import DatabaseService
from services.email_service import EmailService
from services.gemini_service import GeminiService
from services.ocr_service import OCRService
from utils.logger import get_logger

logger = get_logger("invoice_controller")


class InvoiceController:
    """
    Ties all services together.
    Instantiate once and call `run_pipeline()` on each polling cycle.
    """

    def __init__(self) -> None:
        self.email_svc  = EmailService()
        self.ocr_svc    = OCRService()
        self.gemini_svc = GeminiService()
        self.db_svc     = DatabaseService()
        logger.info("InvoiceController initialised — all services ready.")

    # ── main pipeline ───────────────────────────────────────────────────────────

    def run_pipeline(self) -> dict:
        """
        One full polling cycle.
        Returns a summary dict with counts of processed / skipped / failed.
        """
        summary = {"processed": 0, "skipped_duplicate": 0, "failed": 0}

        for attachment in self.email_svc.fetch_invoice_attachments():
            filepath     = attachment["filepath"]
            filename     = attachment["filename"]
            from_address = attachment["from_address"]

            logger.info("── Processing attachment: %s", filename)

            # 1) OCR
            try:
                ocr_text = self.ocr_svc.extract_text(filepath)
            except Exception as exc:
                logger.error("OCR failed for %s: %s", filename, exc)
                summary["failed"] += 1
                continue

            if not ocr_text.strip():
                logger.warning("OCR produced no text for %s — skipping.", filename)
                summary["failed"] += 1
                continue

            # 2) Gemini extraction
            try:
                invoice_data = self.gemini_svc.extract_invoice_data(
                    ocr_text=ocr_text,
                    source_email=from_address,
                    pdf_filename=filename,
                )
            except Exception as exc:
                logger.error("Gemini extraction failed for %s: %s", filename, exc)
                summary["failed"] += 1
                continue

            # 3) Persist
            try:
                inserted_id = self.db_svc.save_invoice(invoice_data)
                if inserted_id:
                    logger.info("✓ Invoice stored | _id: %s", inserted_id)
                    summary["processed"] += 1
                else:
                    logger.info("↷ Duplicate invoice — skipped.")
                    summary["skipped_duplicate"] += 1
            except Exception as exc:
                logger.error("DB save failed for %s: %s", filename, exc)
                summary["failed"] += 1

        logger.info(
            "Pipeline complete | processed=%d  duplicates=%d  failed=%d",
            summary["processed"],
            summary["skipped_duplicate"],
            summary["failed"],
        )
        return summary

    # ── teardown ────────────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        self.db_svc.close()
        logger.info("InvoiceController shut down cleanly.")
