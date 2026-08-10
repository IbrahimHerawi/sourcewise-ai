# SourceWise backend

The SourceWise backend is an asynchronous FastAPI service responsible for authentication,
document ingestion, vector retrieval, grounded answer generation, and persistent question history.
It exposes a versioned JSON API under `/api/v1` and stores application state in PostgreSQL with
pgvector.

[← Project overview](../README.md) · [Frontend guide](../frontend/README.md) ·
[Swagger UI](http://localhost:8000/docs)

## Responsibilities

- Register, verify, authenticate, and recover user accounts.
- Issue short-lived JWT access tokens and rotate opaque refresh-token families.
- Validate and persist all-or-nothing document upload batches.
- Extract text from `.txt`, `.md`, and text-based `.pdf` files.
- Process durable ingestion jobs with bounded asynchronous workers.
- Generate Ollama embeddings and store fixed-dimension vectors in pgvector.
- Retrieve owner-scoped evidence and generate citation-grounded answers.
- Organize documents and questions with optional user-owned collections.
- Deliver local email through SMTP/Mailpit and production email through Resend.

## Architecture

The service uses a layered `src` layout:

```text
backend/
├── alembic/                  Database migration environment and revisions
├── src/app/
│   ├── api/                  FastAPI routers, dependencies, and schemas
│   ├── core/                 Settings, security, logging, middleware, and errors
│   ├── db/                   Async engine, session wiring, and ORM models
│   ├── repositories/         Owner-scoped persistence and query operations
│   ├── services/             Embeddings, email, LLM, and question orchestration
│   ├── utils/                File extraction and deterministic chunking
│   ├── workers/              Durable in-process ingestion workers
│   └── main.py               Application construction and lifecycle
├── tests/                    Unit, API, migration, repository, and smoke tests
├── alembic.ini
├── pyproject.toml
└── uv.lock
```

The boundaries are intentional:

| Layer | Owns | Does not own |
| --- | --- | --- |
| API | HTTP contracts, authentication dependencies, status codes | SQL queries or provider logic |
| Services | Application workflows and external AI/email calls | HTTP response construction |
| Repositories | SQLAlchemy reads, writes, locks, and ownership filters | Request validation |
| Workers | Ingestion scheduling, recovery, and state transitions | API presentation |
| Core | Cross-cutting configuration, security, logging, errors | Feature-specific workflows |

## Core flows

### Document ingestion

1. `POST /api/v1/documents/upload` authenticates a verified user and validates the complete upload
   batch.
2. Files are staged under `UPLOAD_ROOT_DIR/<document_id>/` before their document and ingestion-job
   rows are committed.
3. The endpoint returns `202 Accepted` with documents in `PENDING` state and enqueues their jobs.
4. A worker moves each document and job to `PROCESSING`, extracts text, creates deterministic
   overlapping chunks, and requests ordered Ollama embedding batches.
5. Chunks and vectors are committed atomically before the document becomes `READY` and the job
   becomes `DONE`.
6. Processing failures are recorded on both records. Interrupted `PROCESSING` work is returned to
   `PENDING` and recovered when the API starts again.

Supported input is deliberately narrow:

- `.txt` and `.md` are decoded text documents.
- `.pdf` requires an extractable text layer; OCR is not included.
- `MAX_UPLOAD_MB` limits each file, and an invalid member rejects the entire upload batch.

### Retrieval and answering

1. The question is embedded with Ollama and scoped to the authenticated user and optional
   `collection_id`.
2. pgvector selects a wider candidate set using cosine distance and `vector_cosine_ops`.
3. Candidates are reranked using semantic distance, exact normalized matches, and query-term
   coverage.
4. An evidence gate rejects weak context before an LLM is called. Rejected retrieval produces the
   deterministic response `I could not find the answer in the uploaded documents.`
5. Accepted chunks are packed into a bounded context. The chat provider returns structured claims
   with citation ranks.
6. The service validates those ranks, renders the answer, and atomically persists the answer and
   immutable citation snapshots.

Chat generation is selected with `AI_PROVIDER=ollama` or `AI_PROVIDER=openai`. Embeddings always use
Ollama's native `/api/embed` endpoint so retrieval remains provider-independent.

### Authentication

- Registration stores password hashes and hashed one-time verification tokens.
- Verified, active users receive a short-lived JWT access token and an opaque refresh token.
- Refresh tokens rotate on every successful exchange. Reuse of a consumed token revokes its token
  family.
- Logout revokes the submitted refresh-token family without revealing whether the token existed.
- Password reset invalidates all refresh-token families for the affected user.
- Token-bearing responses use no-store cache headers, and request logs redact sensitive fields.

For local and Docker environments, verification and password-reset messages go to SMTP/Mailpit. In
staging and production, they go through Resend.

## API surface

All paths below are relative to `/api/v1`. Except for health and the account-entry endpoints,
resource operations require `Authorization: Bearer <access_token>` from a verified user.

| Area | Method and path | Purpose |
| --- | --- | --- |
| Health | `GET /health` | Liveness response |
| Authentication | `POST /auth/register` | Create an unverified account |
| Authentication | `POST /auth/verify-email` | Consume a verification token |
| Authentication | `POST /auth/resend-verification` | Replace and resend a verification token |
| Authentication | `POST /auth/login` | Issue an access/refresh token pair |
| Authentication | `POST /auth/refresh` | Rotate a refresh token and issue a new pair |
| Authentication | `POST /auth/logout` | Revoke a refresh-token family |
| Authentication | `GET /auth/me` | Return the authenticated user |
| Authentication | `POST /auth/forgot-password` | Request a password-reset message |
| Authentication | `POST /auth/reset-password` | Consume a reset token and change the password |
| Overview | `GET /auth/overview` | Return owner-scoped resource totals |
| Collections | `POST /collections` | Create a collection |
| Collections | `GET /collections` | List collections with pagination |
| Collections | `GET /collections/{id}` | Return one collection |
| Collections | `PATCH /collections/{id}` | Update a collection |
| Collections | `DELETE /collections/{id}` | Delete a collection without deleting its content |
| Documents | `POST /documents/upload` | Upload one or more documents |
| Documents | `GET /documents` | List documents, optionally by collection |
| Documents | `GET /documents/{id}` | Return document details and processing state |
| Documents | `DELETE /documents/{id}` | Delete a document and its stored file |
| Questions | `POST /questions/ask` | Generate and persist an answer |
| Questions | `GET /questions/history` | List question history, optionally by collection |
| Questions | `GET /questions/history/{id}` | Return an answer and citation snapshots |
| Questions | `DELETE /questions/history/{id}` | Delete one history entry |

Pagination uses `limit` and `offset`; list limits are constrained to `1..100`. Swagger UI at
`/docs` is the authoritative interactive description of request and response schemas.

### Example requests

Check health:

```bash
curl http://localhost:8000/api/v1/health
```

Sign in and copy the returned `access_token`:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"verified@example.com","password":"your-password"}'
```

Ask across every ready document owned by the user:

```bash
curl -X POST http://localhost:8000/api/v1/questions/ask \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the main conclusions?","collection_id":null}'
```

Errors have one stable envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": {
      "errors": []
    }
  }
}
```

## Running the backend

### Complete Docker stack

Use the [root quick start](../README.md#quick-start) for the supported full application. Compose
builds this backend image for both `api` and `migrate`:

- `migrate` waits for a healthy database, runs `uv run alembic upgrade head`, and exits.
- `api` starts only after that migration container exits successfully.
- Uploaded files are bind-mounted from root `data/`; PostgreSQL data lives in a named volume.

### Native development

Native development requires:

- Python 3.13 and [`uv`](https://docs.astral.sh/uv/)
- PostgreSQL with the pgvector extension available
- Ollama reachable from the host
- An SMTP service if you need to inspect account emails

Install dependencies:

```bash
cd backend
uv sync --dev
```

Copy the combined root template into the backend working directory:

```bash
cp ../.env.example .env
```

On PowerShell:

```powershell
Copy-Item ../.env.example .env
```

The root template targets Docker, so replace at least these container paths and service names in
`backend/.env` for host-native development:

```dotenv
APP_ENV=local
LOG_LEVEL=INFO

SECRET_KEY_FILE=

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_DB=app_db
POSTGRES_PASSWORD=replace-with-your-local-password
POSTGRES_PASSWORD_FILE=

AI_PROVIDER=ollama
OLLAMA_OPENAI_BASE_URL=http://localhost:11434/v1
OLLAMA_CHAT_MODEL=llama3.2:1b
OLLAMA_EMBED_MODEL=nomic-embed-text

SMTP_HOST=localhost
SMTP_PORT=1025
UPLOAD_ROOT_DIR=./data/uploads
```

Pull the configured Ollama models, apply migrations, and start the API:

```bash
ollama pull nomic-embed-text
ollama pull llama3.2:1b
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Local mode provides a development-only default signing key when neither `SECRET_KEY` nor
`SECRET_KEY_FILE` is set. Never use that default outside `local`, `test`, or `testing`.

## Configuration

The combined [root `.env.example`](../.env.example) is the source of truth for Docker, backend, and
frontend configuration. Backend settings are case-insensitive and can be supplied through process
environment variables or the `backend/.env` file used during native development. Secret-file
settings take precedence over matching inline secret values.

### Runtime and security

| Setting | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `local` in code | Selects local/test SMTP behavior or staging/production Resend behavior |
| `LOG_LEVEL` | `INFO` | Application and request log level |
| `SECRET_KEY` / `SECRET_KEY_FILE` | Local-only fallback | JWT signing and token hashing secret |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access-token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Absolute refresh-family lifetime |
| `EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES` | `1440` | Verification-token lifetime |
| `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` | `60` | Password-reset-token lifetime |
| `APP_BASE_URL` | `http://localhost:8000` | Public API origin used by the application |
| `FRONTEND_BASE_URL` | `http://localhost:3000` | Origin used to build verification/reset links |

Non-local signing secrets must contain at least 32 characters. The refresh lifetime must be longer
than the access-token lifetime.

### Database, files, and ingestion

| Setting | Default | Purpose |
| --- | --- | --- |
| `POSTGRES_HOST`, `POSTGRES_PORT` | `localhost`, `5432` | PostgreSQL address |
| `POSTGRES_USER`, `POSTGRES_DB` | `postgres`, `app_db` | Database identity |
| `POSTGRES_PASSWORD` / `POSTGRES_PASSWORD_FILE` | Required | Database credential |
| `UPLOAD_ROOT_DIR` | `/data/uploads` | Durable uploaded-file root |
| `MAX_UPLOAD_MB` | `10` | Per-file upload limit |
| `INGEST_WORKERS` | `2` | Concurrent ingestion workers |
| `INGEST_SHUTDOWN_TIMEOUT_S` | `30` | Graceful worker drain timeout |
| `CHUNK_SIZE_CHARS` | `2000` | Deterministic chunk size |
| `CHUNK_OVERLAP_CHARS` | `100` | Character overlap between chunks |

### Retrieval and AI

| Setting | Default | Purpose |
| --- | --- | --- |
| `AI_PROVIDER` | `ollama` | Selects Ollama or OpenAI-compatible chat generation |
| `OLLAMA_CHAT_MODEL` | `llama3.2:1b` | Local chat model |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model used for documents and questions |
| `EMBEDDING_DIM` | `768` | Expected vector length and database column dimension |
| `EMBED_CONCURRENCY` | `4` | Process-wide embedding request concurrency |
| `OLLAMA_EMBED_BATCH_SIZE` | `32` | Ordered document inputs per embedding request |
| `TOP_K` | `5` | Maximum chunks selected for answer context |
| `RETRIEVAL_MAX_COSINE_DISTANCE` | `0.75` | Candidate search cutoff |
| `RETRIEVAL_SEMANTIC_ACCEPT_DISTANCE` | `0.35` | Strong semantic evidence threshold |
| `RETRIEVAL_LEXICAL_ACCEPT_DISTANCE` | `0.55` | Maximum distance eligible for combined lexical evidence |
| `RETRIEVAL_MIN_QUERY_TERM_COVERAGE` | `0.60` | Required lexical term coverage |
| `OPENAI_BASE_URL`, `OPENAI_CHAT_MODEL` | Provider-specific | OpenAI-compatible endpoint and model |
| `OPENAI_API_KEY` / `OPENAI_API_KEY_FILE` | Required for OpenAI | Chat-provider credential |

The embedding client validates response cardinality and vector dimensions. Changing
`EMBEDDING_DIM` after data exists requires a deliberate migration and re-embedding strategy.

### Email

| Environment | Delivery | Required settings |
| --- | --- | --- |
| `test`, `testing` | Disabled | None |
| `local`, `docker` | SMTP | `SMTP_HOST`, `SMTP_PORT`, optional TLS/credentials |
| `staging`, `production` | Resend | `RESEND_API_KEY` or `RESEND_API_KEY_FILE` |

`EMAIL_FROM` controls the sender identity. Production secret files are mounted from the root
`secrets/` directory; see [`secrets/README.md`](../secrets/README.md).

## Database migrations

Run migration commands from `backend/` so Alembic can resolve its configuration and application
package:

```bash
uv run alembic current
uv run alembic upgrade head
uv run alembic history
```

Create a candidate migration after changing ORM metadata:

```bash
uv run alembic revision --autogenerate -m "describe the schema change"
```

Always review generated migrations, verify downgrade behavior, and test upgrades against a real
PostgreSQL/pgvector instance. In Compose, normal API startup runs migrations automatically through
the dedicated one-shot service. `docker compose run --rm migrate` is reserved for an explicit
manual migration run.

## Testing and quality checks

The backend test suite uses Pytest and creates an isolated `pgvector/pgvector:pg16` database with
Testcontainers. A running Docker daemon is therefore required for the complete suite.

```bash
cd backend
uv run pytest -q
uv run pytest tests/test_integration_smoke.py -q
uv run ruff check .
uv run ruff format --check .
```

The suite covers settings and security validation, authentication and refresh rotation, database
migrations, repositories and ownership boundaries, ingestion recovery, embedding/provider failure
modes, retrieval and citation grounding, API contracts, and the end-to-end upload-to-answer flow.

## Operational notes

- `GET /api/v1/health` is a liveness check; Compose separately waits for PostgreSQL and Ollama
  health before starting the API.
- Every response includes or preserves an `X-Request-ID`, and structured request logs record method,
  path, status, and duration.
- The API image runs the in-process ingestion manager. Scaling API replicas requires a separate
  decision about job claiming, worker ownership, and migration execution.
- Collection deletion sets associated documents and questions to uncollected; it does not delete
  their content.
- Citation snapshots are persisted with question history so answers remain explainable after source
  data changes.
