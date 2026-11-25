"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""

from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException
from redis.exceptions import RedisError

from .config import settings
from .redis_client import r


SLIDING_WINDOW = r.register_script("""
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local request_id = ARGV[2]
local window_ms = 60000

local time = redis.call("TIME")
local now_ms = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
redis.call("ZREMRANGEBYSCORE", key, "-inf", now_ms - window_ms)

if redis.call("ZCARD", key) >= limit then
    local oldest = redis.call("ZRANGE", key, 0, 0, "WITHSCORES")
    local retry_ms = oldest[2] and (tonumber(oldest[2]) + window_ms - now_ms) or window_ms
    return math.max(1, math.ceil(retry_ms / 1000))
end

redis.call("ZADD", key, now_ms, request_id)
redis.call("PEXPIRE", key, window_ms)
return 0
""")


def check_rate_limit(key: str) -> None:
    key_hash = sha256(key.encode("utf-8")).hexdigest()

    try:
        retry_after = SLIDING_WINDOW(
            keys=[f"rate:{key_hash}"],
            args=[settings.rate_limit_per_minute, uuid4().hex],
        )
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc

    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
