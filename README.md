# Backend Technical Evaluation API

## 1. Overview
This service accepts document uploads, extracts text, chunks it, and stores embeddings for vector retrieval.  
Questions are answered with a retrieval-augmented generation (RAG) flow that first performs embeddings/vector-search and then calls a chat model with the retrieved context.  
Ingestion runs asynchronously, and each question/answer is persisted with source chunks so question history can be queried later.

## 2. Tech Stack
- FastAPI (Python 3.13)
- PostgreSQL + pgvector for embedding storage and similarity search
- Pydantic + pydantic-settings for configuration
- `uv` for dependency management and execution
- Ollama for local embedding model (`nomic-embed-text`)
- Chat generation via OpenAI Python client with provider switching (`AI_PROVIDER`)

## 3. Project Layout
This project uses a `src/app` package layout with layered architecture.

- `api/`: FastAPI routers and request/response schemas
- `services/`: application logic (RAG orchestration, embeddings, chat calls)
- `repositories/`: database data-access logic
- `workers/`: in-process async ingestion workers
- `utils/`: file extraction and chunking helpers
- `db/`: SQLAlchemy models and session wiring

This structure is intentional for maintainability and separation of concerns.

## 4. Supported File Types
- Supported extensions: `.txt`, `.md`, `.pdf`
- PDF extraction is text-only (no OCR), implemented via `pypdf`
- Upload size limit is controlled by `MAX_UPLOAD_MB` (default: `10`)
- In Docker, files are stored under `/data/uploads/<document_id>/<filename>` (mounted from `./data`)

## 5. RAG Retrieval Details
- Similarity metric: cosine distance (not L2)
- PostgreSQL/pgvector implementation:
  - cosine operator class: `vector_cosine_ops`
  - retrieval ordering by ascending cosine distance
- Chunking strategy: deterministic character-based chunking with overlap
- Chunking parameters are configurable:
  - `CHUNK_SIZE_CHARS`
  - `CHUNK_OVERLAP_CHARS`

## 6. Answering Behavior
The chat model is instructed to answer using only retrieved context.  
If retrieved content is insufficient or irrelevant, the response is a strict unknown-answer fallback: `I don't know based on the uploaded documents.`

## 7. AI Provider Switching
`AI_PROVIDER` controls which chat backend is used.

- `AI_PROVIDER=openai`
  - Uses the external OpenAI API (requires `OPENAI_API_KEY`)
  - Uses `OPENAI_CHAT_MODEL`
- `AI_PROVIDER=ollama`
  - Uses your local Ollama model set in `OLLAMA_CHAT_MODEL` (default `llama3.2:1b`)
  - Requires a running local Ollama service (`OLLAMA_OPENAI_BASE_URL`)

Embeddings are served by Ollama (`OLLAMA_EMBED_MODEL`, default `nomic-embed-text`) for both provider modes.

## 8. Running with Docker
1. Copy environment template:
   ```bash
   cp .env.example .env
   ```
2. Create secret files:
   - `secrets/postgres_password.txt`  The file must contain a non-empty value; empty files will fail startup.
   - `secrets/openai_api_key.txt`   is optional and only needed when `AI_PROVIDER=openai`.
3. Run services in this order:
   ```bash
   docker compose up -d --build db ollama
   docker compose run --rm migrate
   docker compose up -d api
   ```
4. Pull Ollama models (usually once per machine, after `ollama` is running):
   ```bash
   docker compose exec ollama ollama pull nomic-embed-text
   docker compose exec ollama ollama pull llama3.2:1b
   ```

Service URLs:
- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`

## 9. API Usage Examples
Set base URL:

```bash
API_BASE=http://localhost:8000/api/v1
```

Upload document:

```bash
curl -X POST "$API_BASE/documents/upload" \
  -F "file=@./tests/assets/sample.pdf"
```

List documents:

```bash
curl "$API_BASE/documents?limit=20&offset=0"
```

Ask a question:

```bash
curl -X POST "$API_BASE/questions/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does the uploaded document say about office hours?",
    "document_ids": ["<DOCUMENT_UUID_OPTIONAL>"]
  }'
```

Question history:

```bash
curl "$API_BASE/questions/history?limit=20&offset=0"
```

## Demo
- Run (Bash): `API_URL=http://localhost:8000 bash scripts/demo.sh`
- Demonstrates the full flow: upload -> ingestion -> ask -> history
- `demo/` contains the sample `.txt`, `.md`, and `.pdf` files used by the script

## 10. Testing
Run all tests:

```bash
uv run pytest -q
```

Testing approach:
- Unit tests for utilities (file extraction and chunking)
- API tests with mocks for deterministic embeddings/LLM behavior where appropriate
- Integration smoke test for the primary flow (upload -> ingest -> ask -> history)

## 11. Design Decisions Beyond The Evaluation Brief
The evaluation brief requires embeddings/vector-search based retrieval and a README, but it does not explicitly define several implementation details. The following were deliberate choices made to complete the solution reliably:

- Supported file extensions are explicitly constrained to `.txt`, `.md`, `.pdf`
- PDF ingestion uses text-layer extraction only (`pypdf`), with no OCR pipeline
- Similarity metric is cosine distance (chosen instead of L2) and enforced in pgvector query/index configuration
- The assistant is explicitly instructed to return an unknown-answer fallback when context is insufficient, to reduce hallucinations
- Ingestion is handled by an in-process async worker pool with persisted `ingestion_jobs` status for crash recovery and observability
- Vector index strategy prefers HNSW when pgvector version supports it, with IVFFlat fallback (`lists=100`) for compatibility
- Embedding dimension is configurable (`EMBEDDING_DIM`, default `768`) and validated against model output
- Retrieved context is capped before chat generation (`DEFAULT_MAX_CONTEXT_CHARS = 12000`) to keep prompts bounded and predictable
