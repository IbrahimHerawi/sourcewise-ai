# Local Docker Compose Secrets

Create these files locally before running Docker Compose:

- `secrets/openai_api_key.txt`
- `secrets/postgres_password.txt`

Each file must contain only the raw secret value (single line is recommended).

These files are ignored by Git and must never contain committed credentials.
