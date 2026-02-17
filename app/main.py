from app.api import auth_session
from fastapi import FastAPI
from app.api.auth_tiktokshop import router as tiktok_auth_router
from fastapi.middleware.cors import CORSMiddleware

app=FastAPI()

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"message": "Service is healthy"}


app.include_router(tiktok_auth_router)
app.include_router(auth_session.router)
