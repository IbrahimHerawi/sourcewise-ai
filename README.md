# backend-technical-evaluation

## Configuration contract

- Keep non-secret app settings in `.env` (seed from `.env.example`).
- Keep secrets out of `.env.example`.
- The app supports both plain env secrets and Docker-style secret files:
  - `OPENAI_API_KEY_FILE` takes precedence over `OPENAI_API_KEY`
  - `POSTGRES_PASSWORD_FILE` takes precedence over `POSTGRES_PASSWORD`
- The app builds the DB URL from:
  - `POSTGRES_HOST`
  - `POSTGRES_PORT`
  - `POSTGRES_USER`
  - `POSTGRES_DB`
  - `POSTGRES_PASSWORD` or `POSTGRES_PASSWORD_FILE`

## Local development (outside Docker)

1. Copy `.env.example` to `.env`.
2. Keep `.env` non-secret by default; set non-secret app config there.
3. Remove deprecated keys if they still exist in your local `.env`:
   - `DATABASE_URL`
   - `OLLAMA_BASE_URL`
4. Provide secrets with normal environment variables for local runs:
   - `POSTGRES_PASSWORD`
   - `OPENAI_API_KEY` (required only when `AI_PROVIDER=openai`)
5. Set local topology values for non-container runs:
   - `POSTGRES_HOST=localhost`
   - `POSTGRES_PORT=5432`
   - `OLLAMA_OPENAI_BASE_URL=http://localhost:11434/v1`
   - `UPLOAD_ROOT_DIR=/data/uploads` (or a local path if preferred)
6. Start the app with your normal workflow (for example: `uv run uvicorn app.main:app --reload`).

## Docker Compose (with Docker secrets)

1. Copy `.env.example` to `.env` and keep it non-secret.
2. Create local secret files described in [secrets/README.md](secrets/README.md):
   - `secrets/openai_api_key.txt`
   - `secrets/postgres_password.txt`
3. Start services:
   - `docker compose up --build`

Compose wiring in this project:

- App service: `api`
- Postgres service: `db`
- Ollama service: `ollama`
- App container DB host is `db` (not `localhost`)
- Ollama host in app container is `ollama` (not `localhost`)
- Secrets are mounted at:
  - `/run/secrets/openai_api_key`
  - `/run/secrets/postgres_password`

To validate resolved Compose config:

- `docker compose config`
