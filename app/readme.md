# Plantifique Backend (JWT + PostgreSQL)

FastAPI backend for TikTok Shop OAuth where:
- TikTok tokens are stored in PostgreSQL
- frontend receives an app JWT after code exchange
- frontend calls protected APIs with `Authorization: Bearer <jwt>`

## Implemented Auth Flow

1. Frontend sends browser to `GET /auth/tiktokshop/login`
2. Backend creates and stores OAuth `state` in PostgreSQL and redirects to TikTok auth URL
3. TikTok redirects to backend callback: `GET /auth/tiktokshop/callback?code=...&state=...`
4. Backend validates state, then redirects to frontend callback route with `code` + `state`
5. Frontend callback page calls `POST /auth/tiktokshop/exchange` with `code/state`
6. Backend exchanges code with TikTok, stores `access_token`/`refresh_token` in PostgreSQL, creates app JWT
7. Backend returns `{ access_token, user }`
8. Frontend stores JWT and uses it for `/auth/me` and protected APIs

## API Endpoints

- `GET /` health
- `GET /auth/tiktokshop/login`
- `GET /auth/tiktokshop/callback`
- `POST /auth/tiktokshop/exchange`
- `GET /auth/me` (JWT required)
- `POST /auth/logout` (client-side logout marker endpoint)

## Backend Files Added/Updated

- `app/core/config.py`
- `app/db/database.py`
- `app/db/models.py`
- `app/schemas/auth.py`
- `app/utils/security.py`
- `app/services/tiktokshop_oauth.py`
- `app/api/auth_tiktokshop.py`
- `app/api/auth_session.py`
- `app/main.py`
- `app/requirements.txt`

## PostgreSQL Setup

1. Install PostgreSQL and create DB:
   ```sql
   CREATE DATABASE plantifique;
   ```
2. Ensure user/password in `DATABASE_URL` has access.

## Environment Variables (`app/.env`)

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/plantifique
APP_KEY=your_tiktok_app_key
APP_SECRET=your_tiktok_app_secret
REDIRECT_URI=http://localhost:8000/auth/tiktokshop/callback
AUTH_URL=https://auth.tiktok-shops.com/oauth/authorize
TOKEN_URL=https://auth.tiktok-shops.com/api/v2/token/get
FRONTEND_URL=http://localhost:5173
FRONTEND_OAUTH_CALLBACK_PATH=/auth/tiktokshop/callback
JWT_SECRET_KEY=replace_with_long_random_secret
JWT_ALGORITHM=HS256
JWT_EXP_MINUTES=60
```

Important:
- `REDIRECT_URI` must exactly match TikTok developer console redirect URI.
- For local dev, keep frontend callback route as `/auth/tiktokshop/callback`.

## Install and Run

From project root (`Plantifique`):

1. Create venv and activate:
   ```bash
   cd app
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start API:
   ```bash
   cd ..
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
4. Open docs:
   - `http://localhost:8000/docs`

## CORS

`app/main.py` already allows:
- `http://localhost:5173`
- `http://127.0.0.1:5173`

## Notes

- This implementation stores TikTok tokens in DB and app JWT on frontend (localStorage).
- For production hardening, add token encryption at rest, refresh flow, JWT revocation/blacklist, and Alembic migrations.
