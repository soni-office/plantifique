import logging
from typing import Any
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

class TokenUsageCallbackHandler(BaseCallbackHandler):
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        try:
            for generation_list in response.generations:
                for gen in generation_list:
                    if hasattr(gen, "message") and hasattr(gen.message, "usage_metadata") and gen.message.usage_metadata is not None:
                        usage = gen.message.usage_metadata
                        logger.info(
                            "[Gemini Token Usage] Input: %s | Output: %s | Total: %s",
                            usage.get("input_tokens", 0),
                            usage.get("output_tokens", 0),
                            usage.get("total_tokens", 0)
                        )
        except Exception as e:
            # We don't want a logging error to break our AI analysis
            logger.debug("Failed to extract token usage: %s", e)
