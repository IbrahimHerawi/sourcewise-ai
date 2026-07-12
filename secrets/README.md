# Local Docker Compose Secrets

Create this required file locally before running Docker Compose:

- `secrets/postgres_password.txt`
- `secrets/secret_key.txt` (at least 32 characters)

Optional (only when `AI_PROVIDER=openai`):

- `secrets/openai_api_key.txt`
- Set `OPENAI_API_KEY_FILE=/app-secrets/openai_api_key.txt` in `.env`.

Required only for staging/production Resend email:

- `secrets/resend_api_key.txt`
- Set `RESEND_API_KEY_FILE=/app-secrets/resend_api_key.txt` in `.env`.

Each present file must contain only the raw secret value (single line is recommended).

These files are ignored by Git and must never contain committed credentials.
Do not put API key values directly in `.env`; use the `*_FILE` variables above.
