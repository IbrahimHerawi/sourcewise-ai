# Local Docker Compose Secrets

Create this required file locally before running Docker Compose:

- `secrets/postgres_password.txt`

Optional (only when `AI_PROVIDER=openai`):

- `secrets/openai_api_key.txt`
- This file is mounted to `/app-secrets/openai_api_key.txt` in `api` and `migrate` containers.

Each present file must contain only the raw secret value (single line is recommended).

These files are ignored by Git and must never contain committed credentials.
