"""
services/database_service.py
MongoDB persistence layer for invoice documents.
"""
from datetime import datetime, timezone
from typing import Optional

from pymongo import MongoClient, errors
from pymongo.collection import Collection

from config.settings import MONGO_CONFIG
from utils.logger import get_logger

logger = get_logger("database_service")


class DatabaseService:
    """Handles all MongoDB operations for the invoices collection."""

    def __init__(self) -> None:
        self._client: Optional[MongoClient] = None
        self._collection: Optional[Collection] = None
        self._connect()

    # ── connection ──────────────────────────────────────────────────────────────

    def _connect(self) -> None:
        try:
            self._client = MongoClient(
                MONGO_CONFIG["uri"],
                serverSelectionTimeoutMS=5000,
            )
            # Verify connectivity
            self._client.admin.command("ping")
            db = self._client[MONGO_CONFIG["db_name"]]
            self._collection = db[MONGO_CONFIG["collection"]]
            self._ensure_indexes()
            logger.info(
                "MongoDB connected | DB: %s | Collection: %s",
                MONGO_CONFIG["db_name"],
                MONGO_CONFIG["collection"],
            )
        except errors.ServerSelectionTimeoutError as exc:
            logger.error("MongoDB connection failed: %s", exc)
            raise

    def _ensure_indexes(self) -> None:
        """Create a unique index on invoice_number to prevent duplicates."""
        self._collection.create_index(
            "invoice_number",
            unique=True,
            sparse=True,   # allows multiple null invoice_numbers
        )
        # Useful query indexes
        self._collection.create_index("processed_at")
        self._collection.create_index("vendor_name")
        logger.debug("MongoDB indexes ensured.")

    # ── CRUD ────────────────────────────────────────────────────────────────────

    def save_invoice(self, invoice_data: dict) -> Optional[str]:
        """
        Insert an invoice document.
        Returns the inserted _id as string, or None if it's a duplicate.
        Raises on other database errors.
        """
        try:
            result = self._collection.insert_one(invoice_data)
            inserted_id = str(result.inserted_id)
            logger.info("Invoice saved | _id: %s | Number: %s", inserted_id, invoice_data.get("invoice_number"))
            return inserted_id
        except errors.DuplicateKeyError:
            logger.warning(
                "Duplicate invoice skipped | Number: %s",
                invoice_data.get("invoice_number"),
            )
            return None
        except errors.PyMongoError as exc:
            logger.error("MongoDB insert error: %s", exc)
            raise

    def invoice_exists(self, invoice_number: str) -> bool:
        """Quick existence check by invoice_number."""
        return self._collection.count_documents({"invoice_number": invoice_number}, limit=1) > 0

    def get_all_invoices(self, limit: int = 100) -> list[dict]:
        cursor = self._collection.find({}, {"_id": 0}).sort("processed_at", -1).limit(limit)
        return list(cursor)

    def get_invoice_by_number(self, invoice_number: str) -> Optional[dict]:
        return self._collection.find_one({"invoice_number": invoice_number}, {"_id": 0})

    # ── teardown ────────────────────────────────────────────────────────────────

    def close(self) -> None:
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed.")
