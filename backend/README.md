# Sourcewise API

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
The backend uses a `backend/src/app` package layout with layered architecture.

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
  - `CHUNK_SIZE_CHARS` (default: `2000`)
  - `CHUNK_OVERLAP_CHARS` (default: `100`)

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

Embeddings are served by Ollama (`OLLAMA_EMBED_MODEL`, default `nomic-embed-text`) for both provider modes. Document chunks use ordered, sequential requests to Ollama's native `/api/embed` endpoint, with up to `OLLAMA_EMBED_BATCH_SIZE` inputs per request (default: `32`). `EMBED_CONCURRENCY` limits concurrent embedding HTTP requests process-wide across ingestion workers and queries, and `OLLAMA_EMBED_READ_TIMEOUT_S` defaults to `120` seconds. Ollama receives `truncate=false`, so oversized inputs fail instead of being silently truncated.

## 8. Email Verification Delivery
Registration and verification-email resends store only hashed verification tokens and send verification emails. Clients consume the raw one-time token through `POST /api/v1/auth/verify-email` and can request a replacement through `POST /api/v1/auth/resend-verification`.

`APP_ENV` selects the email provider:

- `APP_ENV=test` or `APP_ENV=testing`: email sending is disabled for tests.
- `APP_ENV=local` or `APP_ENV=docker`: email is sent through SMTP to Mailpit.
- `APP_ENV=staging` or `APP_ENV=production`: email is sent through Resend.

Local Docker development uses Mailpit:

- SMTP host: `mailpit`
- SMTP port: `1025`
- SMTP TLS: `false`
- Mailpit UI: `http://localhost:8025`
- These values should come from the root `.env` file used by Docker Compose.

Staging and production use Resend:

- Required sender domain: `notifications.ibrahimherawi.com`
- Required sender: `Sourcewise <no-reply@notifications.ibrahimherawi.com>`
- Required secret file in containers: `/app-secrets/resend_api_key.txt`
- Production frontend URL: `https://sourcewise.ibrahimherawi.com`
- Do not put the Resend API key value in `.env`; put it in `secrets/resend_api_key.txt`.

Local Docker Mailpit `.env` values:

```bash
APP_ENV=docker
FRONTEND_BASE_URL=http://localhost:3000
EMAIL_FROM=Sourcewise <no-reply@notifications.ibrahimherawi.com>
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USE_TLS=false
RESEND_API_KEY_FILE=/app-secrets/resend_api_key.txt
```

Production container environments should use:

```bash
APP_ENV=production
RESEND_API_KEY_FILE=/app-secrets/resend_api_key.txt
FRONTEND_BASE_URL=https://sourcewise.ibrahimherawi.com
EMAIL_FROM=Sourcewise <no-reply@notifications.ibrahimherawi.com>
```

Do not use `APP_ENV=docker` for a publicly deployed container. That value is only for local Docker Compose development.

## 9. Running with Docker
Docker Compose remains at the repository root.

1. Copy environment template:
   ```bash
   cp backend/.env.example .env
   ```
   The `.env` file should contain configuration and secret-file paths only. Keep actual secret values in files under `secrets/`.
2. Create secret files:
   - `secrets/postgres_password.txt`  The file must contain a non-empty value; empty files will fail startup.
   - `secrets/secret_key.txt`  Required for Docker/non-local runs; use a high-entropy value of at least 32 characters.
   - `secrets/openai_api_key.txt`   is optional and only needed when `AI_PROVIDER=openai`.
   - `secrets/resend_api_key.txt` is required only when `APP_ENV=staging` or `APP_ENV=production`, and is mounted as `/app-secrets/resend_api_key.txt`.
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
- Mailpit UI: `http://localhost:8025`

## 10. API Usage Examples
Set base URL:

```bash
API_BASE=http://localhost:8000/api/v1
ACCESS_TOKEN=<VERIFIED_USER_ACCESS_TOKEN>
COLLECTION_ID=<COLLECTION_UUID_OPTIONAL>
```

Upload document:

```bash
curl -X POST "$API_BASE/documents/upload" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "files=@./backend/tests/assets/sample.pdf" \
  -F "files=@./demo/sample.txt" \
  -F "collection_id=$COLLECTION_ID"
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

## 11. Testing
Run all tests from the backend directory:

```bash
cd backend
uv run pytest -q
```

Testing approach:
- Unit tests for utilities (file extraction and chunking)
- API tests with mocks for deterministic embeddings/LLM behavior where appropriate
- Integration smoke test for the primary flow (upload -> ingest -> ask -> history)

## 12. Design Decisions Beyond The Evaluation Brief
The evaluation brief requires embeddings/vector-search based retrieval and a README, but it does not explicitly define several implementation details. The following were deliberate choices made to complete the solution reliably:

- Supported file extensions are explicitly constrained to `.txt`, `.md`, `.pdf`
- PDF ingestion uses text-layer extraction only (`pypdf`), with no OCR pipeline
- Similarity metric is cosine distance (chosen instead of L2) and enforced in pgvector query/index configuration
- The assistant is explicitly instructed to return an unknown-answer fallback when context is insufficient, to reduce hallucinations
- Ingestion is handled by an in-process async worker pool with persisted `ingestion_jobs` status for crash recovery and observability
- Worker shutdown drains for up to `INGEST_SHUTDOWN_TIMEOUT_S` (default `30`) before cancelling workers; interrupted `PROCESSING` jobs are recovered on the next startup
- Vector index strategy prefers HNSW when pgvector version supports it, with IVFFlat fallback (`lists=100`) for compatibility
- Embedding dimension is configurable (`EMBEDDING_DIM`, default `768`) and validated against model output
- Retrieved context is capped before chat generation (`DEFAULT_MAX_CONTEXT_CHARS = 12000`) to keep prompts bounded and predictable
