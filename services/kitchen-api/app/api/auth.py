from collections.abc import Callable

from fastapi import APIRouter, Depends, Request, status

from app.core.config import settings
from app.core.rate_limit import InMemoryRateLimiter
from app.infrastructure.clients.email import EmailClient
from app.infrastructure.database.session import async_session_maker
from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.auth import (
    MessageResponse,
    RegistrationRequest,
    ResendVerificationRequest,
    VerifyEmailRequest,
)
from app.services.errors import RateLimitExceeded
from app.services.registration import RegistrationService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_rate_limiter = InMemoryRateLimiter(
    max_buckets=settings.AUTH_RATE_LIMIT_MAX_BUCKETS,
    cleanup_interval_seconds=(
        settings.AUTH_RATE_LIMIT_CLEANUP_INTERVAL_SECONDS
    ),
)
_email_client = EmailClient(
    host=settings.SMTP_HOST,
    port=settings.SMTP_PORT,
    sender=settings.SMTP_SENDER,
    timeout=settings.SMTP_TIMEOUT_SECONDS,
    use_tls=settings.SMTP_USE_TLS,
    start_tls=settings.SMTP_START_TLS,
    validate_certs=settings.SMTP_VALIDATE_CERTS,
    base_url=settings.EMAIL_VERIFICATION_BASE_URL,
    username=settings.SMTP_USERNAME,
    password=settings.SMTP_PASSWORD,
)


def get_uow_factory() -> Callable[[], UnitOfWork]:
    return lambda: UnitOfWork(async_session_maker)


async def _enforce_rate_limit(
    request: Request,
    scope: str,
    limit: int,
) -> None:
    client_ip = (
        request.client.host if request.client is not None else "unknown"
    )
    retry_after = await _rate_limiter.check(
        scope,
        client_ip,
        limit,
        settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )
    if retry_after is not None:
        raise RateLimitExceeded(retry_after)


def _service() -> RegistrationService:
    return RegistrationService(_email_client)


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
        request,
        "auth-resend-verification",
        settings.AUTH_RESEND_RATE_LIMIT,
    )


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_limit_registration)],
)
async def register(
    body: RegistrationRequest,
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> MessageResponse:
    await _service().register(uow_factory, str(body.email), body.password)
    return MessageResponse(
        message=(
            "If registration is available, a verification email will be sent"
        )
    )


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    dependencies=[Depends(_limit_verification)],
)
async def verify_email(
    body: VerifyEmailRequest,
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> MessageResponse:
    await _service().verify_email(uow_factory, body.token, body.password)
    return MessageResponse(message="Email successfully verified")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_limit_resend)],
)
async def resend_verification(
    body: ResendVerificationRequest,
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> MessageResponse:
    await _service().resend_verification(uow_factory, str(body.email))
    return MessageResponse(
        message="If verification is available, an email will be sent"
    )
