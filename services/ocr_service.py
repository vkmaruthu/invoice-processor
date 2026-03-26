"""
services/ocr_service.py
OCR layer — converts PDF pages and images to plain text.

Strategy (in order):
  1. pdfplumber  — fast native text extraction for digital PDFs
  2. docTR       — deep-learning OCR for scanned PDFs and images
                   (no Tesseract binary required; works on Windows out of the box)
"""
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("ocr_service")

# ── optional imports ───────────────────────────────────────────────────────────
try:
    import pdfplumber
    _PDFPLUMBER_OK = True
except ImportError:
    _PDFPLUMBER_OK = False
    logger.warning("pdfplumber not installed — native PDF text extraction unavailable.")

try:
    import numpy as np
    from PIL import Image
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor
    _DOCTR_OK = True
except ImportError:
    _DOCTR_OK = False
    logger.warning("docTR not installed — OCR unavailable. Run: pip install python-doctr[torch]")


class OCRService:
    """Extract text from PDF / image attachments using docTR."""

    def __init__(self) -> None:
        self._model = None          # lazy-loaded on first use (heavy to import)

    # ── public API ──────────────────────────────────────────────────────────────

    def extract_text(self, filepath: str) -> str:
        """Return extracted text or raise RuntimeError on total failure."""
        ext = Path(filepath).suffix.lower()
        if ext == ".pdf":
            return self._extract_from_pdf(filepath)
        elif ext in {".jpg", ".jpeg", ".png"}:
            return self._extract_from_image(filepath)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    # ── PDF ─────────────────────────────────────────────────────────────────────

    def _extract_from_pdf(self, filepath: str) -> str:
        # 1) Fast path: native text layer (digital PDFs)
        if _PDFPLUMBER_OK:
            try:
                text = self._pdfplumber_extract(filepath)
                if text.strip():
                    logger.info("PDF text extracted via pdfplumber (digital PDF).")
                    return text
                logger.info("pdfplumber found no text — falling back to docTR OCR.")
            except Exception as exc:
                logger.warning("pdfplumber failed: %s", exc)

        # 2) docTR OCR (scanned / image-only PDFs)
        if not _DOCTR_OK:
            raise RuntimeError(
                "docTR is not installed. Run: pip install python-doctr[torch]"
            )
        try:
            return self._doctr_extract_pdf(filepath)
        except Exception as exc:
            raise RuntimeError(f"docTR PDF OCR failed for {filepath}: {exc}") from exc

    def _pdfplumber_extract(self, filepath: str) -> str:
        pages = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return "\n".join(pages)

    def _doctr_extract_pdf(self, filepath: str) -> str:
        logger.info("Running docTR OCR on PDF: %s", filepath)
        model  = self._get_model()
        doc    = DocumentFile.from_pdf(filepath)
        result = model(doc)
        return self._doctr_result_to_text(result)

    # ── Image ────────────────────────────────────────────────────────────────────

    def _extract_from_image(self, filepath: str) -> str:
        if not _DOCTR_OK:
            raise RuntimeError(
                "docTR is not installed. Run: pip install python-doctr[torch]"
            )
        try:
            logger.info("Running docTR OCR on image: %s", filepath)
            model  = self._get_model()
            doc    = DocumentFile.from_images(filepath)
            result = model(doc)
            text   = self._doctr_result_to_text(result)
            logger.info("Image OCR complete: %s", filepath)
            return text
        except Exception as exc:
            raise RuntimeError(f"docTR image OCR failed for {filepath}: {exc}") from exc

    # ── docTR helpers ────────────────────────────────────────────────────────────

    def _get_model(self):
        """Lazy-load the docTR predictor (downloads weights on first call)."""
        if self._model is None:
            logger.info("Loading docTR OCR model (first run may download weights) …")
            self._model = ocr_predictor(
                det_arch="db_resnet50",     # text detection backbone
                reco_arch="crnn_vgg16_bn",  # text recognition backbone
                pretrained=True,
            )
            logger.info("docTR model loaded.")
        return self._model

    @staticmethod
    def _doctr_result_to_text(result) -> str:
        """
        Flatten a docTR Document result into a plain string.
        Preserves page → block → line → word hierarchy as newlines.
        """
        lines = []
        for page in result.pages:
            for block in page.blocks:
                for line in block.lines:
                    words = " ".join(word.value for word in line.words)
                    lines.append(words)
                lines.append("")    # blank line between blocks
        return "\n".join(lines).strip()
