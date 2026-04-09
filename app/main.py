from app.core.config import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import sample_request
from app.api import creator
from app.api import auth_session
from app.api import agent
from app.api import product
from app.api import internal
from app.api import org
from app.api import tier_config
from app.api.auth_tiktokshop import router as tiktok_auth_router
import logging

# This configures all your child loggers at once
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s - %(message)s"
)
app = FastAPI()

origins = settings.allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/')
def health_check():
    return {'message': 'Service is healthy'}


app.include_router(tiktok_auth_router)
app.include_router(auth_session.router)
app.include_router(sample_request.router)
app.include_router(product.router)
app.include_router(agent.router)
app.include_router(creator.router)
app.include_router(internal.router)
app.include_router(org.router)
app.include_router(tier_config.router)