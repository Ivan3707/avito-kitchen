from fastapi import Request

from app.core.config import settings
from app.core.errors import RateLimitExceeded


async def _enforce_rate_limit(
    request: Request, scope: str, limit: int
) -> None:
    client_ip = (
        request.client.host if request.client is not None else "unknown"
    )
    retry_after = await request.app.state.rate_limiter.check(
        scope, client_ip, limit, settings.AUTH_RATE_LIMIT_WINDOW_SECONDS
    )
    if retry_after is not None:
        raise RateLimitExceeded(retry_after)


async def _limit_registration(request: Request) -> None:
    await _enforce_rate_limit(
        request, "auth-register", settings.AUTH_REGISTER_RATE_LIMIT
    )


async def _limit_verification(request: Request) -> None:
    await _enforce_rate_limit(
        request, "auth-verify-email", settings.AUTH_VERIFY_RATE_LIMIT
    )


async def _limit_resend(request: Request) -> None:
    await _enforce_rate_limit(
        request, "auth-resend-verification", settings.AUTH_RESEND_RATE_LIMIT
    )
