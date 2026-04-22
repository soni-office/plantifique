import time
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import sample_request, creator, auth_session, agent, product, internal, org, testing, tier_config
from app.api.auth_tiktokshop import router as tiktok_auth_router

# This configures all your child loggers at once
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: [w%(process)d]  %(name)s - %(message)s"
    # format="%(levelname)s: [w%(process)d] %(asctime)s %(name)s - %(message)s",
    # datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("api.timing")

app = FastAPI()


# @app.middleware("http")
# async def log_request_timing(request: Request, call_next):
#     start = time.perf_counter()
#     response = await call_next(request)
#     elapsed_ms = (time.perf_counter() - start) * 1000
#     logger.info(
#         "%s %s → %d  [%.1f ms]",
#         request.method,
#         request.url.path,
#         response.status_code,
#         elapsed_ms,
#     )
#     return response

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
app.include_router(testing.router)
