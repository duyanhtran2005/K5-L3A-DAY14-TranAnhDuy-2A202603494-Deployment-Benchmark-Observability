"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from redis.exceptions import RedisError

from .config import settings
from .redis_client import r


PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006
BUDGET_KEY_TTL_SECONDS = 2 * 24 * 60 * 60


def estimate_tokens(text: str) -> int:
    return (len(text) + 3) // 4


def check_budget() -> str:
    day = datetime.now(timezone.utc).date().isoformat()
    budget_key = f"budget:daily:{day}"

    try:
        spent = float(r.get(budget_key) or 0)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc

    if spent >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")

    return budget_key


def record_cost(budget_key: str, input_tokens: int, output_tokens: int) -> None:
    cost_usd = (
        input_tokens * PRICE_INPUT_PER_1K
        + output_tokens * PRICE_OUTPUT_PER_1K
    ) / 1000

    try:
        with r.pipeline(transaction=True) as pipe:
            pipe.incrbyfloat(budget_key, cost_usd)
            pipe.expire(budget_key, BUDGET_KEY_TTL_SECONDS)
            pipe.execute()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc