"""Background workers package."""

from app.workers.ingestion import IngestionManager

__all__ = ["IngestionManager"]
