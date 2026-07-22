"""
llm.py

Instantiates every chat model used in this project. Every agent should
import its model from here rather than calling init_chat_model directly.
"""

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.rate_limiters import InMemoryRateLimiter

import config

load_dotenv()

rate_limiter=InMemoryRateLimiter(
    requests_per_second=1/30,  #one call every 30 seconds
    check_every_n_seconds=1,
    max_bucket_size=1,  
)

gemini_model=init_chat_model(
    config.GEMINI_MODEL_NAME,
    model_provider=config.GEMINI_MODEL_PROVIDER,
    temperature=config.GEMINI_TEMPERATURE,
    max_tokens=config.GEMINI_MAX_TOKENS,
    thinking_level=config.GEMINI_THINKING_LEVEL,
    #rate_limiter=rate_limiter 
)

open_router_model=init_chat_model(
    config.OPENROUTER_MODEL_NAME,
    model_provider=config.OPENROUTER_MODEL_PROVIDER,
    temperature=config.OPENROUTER_TEMPERATURE,
    max_tokens=config.OPENROUTER_MAX_TOKENS,
)
