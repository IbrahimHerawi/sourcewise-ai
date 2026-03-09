# Reviewer Demo Reference

## Ingestion Pipeline
- Ingestion runs asynchronously through an in-process worker pool.
- Ingestion job status is persisted so failures are observable and recoverable.

## Config Snapshot
- `CHUNK_SIZE_CHARS` defaults to `1200`.
- `CHUNK_OVERLAP_CHARS` defaults to `200`.
