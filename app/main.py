from fastapi import FastAPI
from app.api.seller import router as seller_router
app=FastAPI()

@app.get("/")
def health_check():
    return {"message": "Service is healthy"}


app.include_router(seller_router, prefix="/seller")