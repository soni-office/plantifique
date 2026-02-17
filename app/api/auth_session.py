from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Auth Session"])

@router.get("/me")
def me():
    # later you will return real user info from DB/session
    return {
        "id": "demo-user",
        "email": "demo@example.com",
        "username": "tiktok-user"
    }
