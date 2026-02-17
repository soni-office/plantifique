# Plantifique Backend

FastAPI backend for TikTok Shop OAuth integration.

## Stack

- Python 3.10+
- FastAPI
- Uvicorn
- requests
- python-dotenv

## Project Structure

```text
app/
  api/
    auth_tiktokshop.py
    auth_session.py
  services/
    tiktokshop_oauth.py
  utils/
    api_sign.py
  main.py
  .env
  requirements.txt
```

## Local Setup

1. Create and activate virtual environment:
   - macOS/Linux:
     ```bash
     cd app
     python3 -m venv .venv
     source .venv/bin/activate
     ```

2. Install dependencies:
   ```bash
   pip install fastapi uvicorn requests python-dotenv
   ```

3. Configure environment variables in `app/.env`.

4. Run server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. Open docs:
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

## Environment Variables

Current expected variables:

```env
APP_KEY=your_tiktok_app_key
APP_SECRET=your_tiktok_app_secret
REDIRECT_URI=http://localhost:8000/auth/tiktokshop/callback
AUTH_URL=https://auth.tiktok-shops.com/oauth/authorize
TOKEN_URL=https://auth.tiktok-shops.com/api/v2/token/get
FRONTEND_URL=http://localhost:5173/dashboard
```

Notes:
- `REDIRECT_URI` must exactly match both:
  - TikTok developer console redirect URI
  - backend callback route in `auth_tiktokshop.py`
- In your current code, callback route is `/auth/tiktokshop/callback`.

## API Endpoints

### Health

- `GET /`
- Response:
  ```json
  { "message": "Service is healthy" }
  ```

### OAuth Login

- `GET /auth/tiktokshop/login`
- Behavior: redirects seller to TikTok authorization page (`302`).

### OAuth Callback

- `GET /auth/tiktokshop/callback?code=...&state=...`
- Behavior:
  - exchanges auth code for access/refresh token
  - redirects to frontend dashboard (`FRONTEND_URL`)

### Session User

- `GET /auth/me`
- Current response is a demo user payload.

## OAuth Flow

1. Frontend navigates to `GET /auth/tiktokshop/login`.
2. Backend redirects to TikTok OAuth authorize URL.
3. User authorizes in TikTok.
4. TikTok redirects to backend callback (`REDIRECT_URI`).
5. Backend exchanges code for token and redirects to frontend dashboard.

## CORS Configuration

`main.py` currently allows:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

and `allow_credentials=True`, so cookie/session auth can work with the frontend.

## Common Issues

1. Redirect loop to frontend login:
   - ensure backend callback is hit successfully
   - ensure frontend auth check endpoint (`/auth/me`) returns authenticated user/session

2. `302` from TikTok authorize URL:
   - normal OAuth redirect behavior

3. Callback mismatch:
   - if `.env` has `REDIRECT_URI=/auth/tiktok/callback` but router uses `/auth/tiktokshop/callback`, OAuth will fail
   - make them identical

## Next Backend Hardening Steps

- Validate `state` parameter against a stored value (CSRF protection)
- Add robust error handling around token exchange
- Store access/refresh tokens securely in DB/Redis
- Replace demo `/auth/me` with real session/JWT user lookup
- Add structured logging instead of `print`
