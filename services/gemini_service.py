"""
services/gemini_service.py
Uses Google Gemini to parse raw OCR text into structured invoice JSON.
"""
import json
import re
from datetime import datetime, timezone

import google.generativeai as genai

from config.settings import GEMINI_CONFIG
from utils.logger import get_logger

logger = get_logger("gemini_service")

# ── Prompt template ────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are an expert invoice data extraction AI.
Given raw OCR text from an invoice document, extract all relevant fields and
return ONLY a valid JSON object — no markdown fences, no explanation.

The JSON must follow this schema exactly:
{
  "invoice_number":  string or null,
  "invoice_date":    "YYYY-MM-DD" or null,
  "due_date":        "YYYY-MM-DD" or null,
  "vendor_name":     string or null,
  "vendor_email":    string or null,
  "customer_name":   string or null,
  "line_items": [
    {
      "description": string,
      "quantity":    number,
      "unit_price":  number,
      "total":       number
    }
  ],
  "subtotal":        number or null,
  "tax_percentage":  number or null,
  "tax_amount":      number or null,
  "total_amount":    number or null,
  "currency":        string or null
}

Rules:
- Use null for any field you cannot confidently extract.
- Dates must be in ISO 8601 format (YYYY-MM-DD).
- Numbers must be plain numerics (no currency symbols, no commas).
- line_items must be an array (empty array [] if none found).
- Do NOT add extra fields.
"""


class GeminiService:
    """Sends OCR text to Gemini and returns a structured invoice dict."""

    def __init__(self) -> None:
        api_key = GEMINI_CONFIG["api_key"]
        if not api_key or api_key == "your_gemini_api_key":
            raise ValueError("GEMINI_API_KEY is not configured in .env")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=GEMINI_CONFIG["model"],
            system_instruction=_SYSTEM_PROMPT,
        )
        logger.info("Gemini model initialised: %s", GEMINI_CONFIG["model"])

    # ── public API ──────────────────────────────────────────────────────────────

    def extract_invoice_data(
        self,
        ocr_text: str,
        source_email: str = "",
        pdf_filename: str = "",
    ) -> dict:
        """
        Returns a fully populated invoice dict ready for MongoDB insertion.
        Raises RuntimeError if Gemini fails or returns unparseable JSON.
        """
        if not ocr_text.strip():
            raise ValueError("OCR text is empty — nothing to extract.")

        prompt = f"Extract the invoice data from the following OCR text:\n\n{ocr_text}"

        logger.info("Sending OCR text to Gemini (%d chars) …", len(ocr_text))
        try:
            response = self.model.generate_content(prompt)
            raw_json = response.text.strip()
        except Exception as exc:
            raise RuntimeError(f"Gemini API call failed: {exc}") from exc

        invoice_data = self._parse_json(raw_json)

        # ── Enrich with metadata ───────────────────────────────────────────────
        invoice_data["source_email"]  = source_email
        invoice_data["pdf_filename"]  = pdf_filename
        invoice_data["processed_at"]  = datetime.now(timezone.utc).isoformat()
        invoice_data["status"]        = "processed"

        logger.info(
            "Invoice extracted | Number: %s | Total: %s %s",
            invoice_data.get("invoice_number"),
            invoice_data.get("currency"),
            invoice_data.get("total_amount"),
        )
        return invoice_data

    # ── helpers ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Strip optional markdown fences and parse JSON."""
        # Remove ```json … ``` wrappers if present
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Gemini returned invalid JSON: {exc}\nRaw response:\n{raw}"
            ) from exc
