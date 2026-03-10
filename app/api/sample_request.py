from fastapi import APIRouter, Depends, Query
import logging

from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.sample_service import TikTokSampleService
from app.utils.shop_ciphers import shop_cipher

router = APIRouter(prefix="/tiktok/samples", tags=["TikTok Sample Requests"])

logger = logging.getLogger(__name__)


@router.get("/search")
async def search_sample_requests(
    page_size: int = Query(20),
    user=Depends(get_current_user),
):
    token_service = TokenService()
    access_token = token_service.get_valid_access_token(user["id"])
    res = shop_cipher(user["id"])
    cipher = res["data"]["shops"][0]["cipher"]
    logger.info("Searching sample requests for user=%s", user["id"])

    return TikTokSampleService.search(
        access_token=access_token,
        shop_cipher=cipher,
        page_size=page_size,
    )


@router.post("/{sample_id}/evaluate")
async def evaluate_sample_request(
    sample_id: str,
    threshold: int = Query(70, description="Minimum score required to accept"),
    user=Depends(get_current_user),
):

    from app.agents.sample_analyzer.runner import run_sr_agent
    
    logger.info("Evaluating sample request id=%s for user=%s", sample_id, user["id"])
    
    try:
        # Fetch the authentication tokens for this user
        token_service = TokenService()
        access_token = token_service.get_valid_access_token(user["id"])
        res = shop_cipher(user["id"])
        cipher = res["data"]["shops"][0]["cipher"]

        # Run the agent with live tokens
        result = run_sr_agent(
            sample_request_id=sample_id, 
            access_token=access_token, 
            shop_cipher=cipher, 
            threshold=threshold
        )
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error evaluating sample request: {e}")
        return {"status": "error", "message": str(e)}