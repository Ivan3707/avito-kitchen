from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_registration_service
from app.modules.auth.dependencies import (
    _limit_registration,
    _limit_resend,
    _limit_verification,
)
from app.modules.auth.registration import RegistrationService
from app.modules.auth.schemas import (
    MessageResponse,
    RegistrationRequest,
    ResendVerificationRequest,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_limit_registration)],
)
async def register(
    body: RegistrationRequest,
    service: RegistrationService = Depends(get_registration_service),
) -> MessageResponse:
    await service.register(str(body.email), body.password)
    return MessageResponse(
        message="If registration is available, a verification email will be sent"
    )


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    dependencies=[Depends(_limit_verification)],
)
async def verify_email(
    body: VerifyEmailRequest,
    service: RegistrationService = Depends(get_registration_service),
) -> MessageResponse:
    await service.verify_email(body.token, body.password)
    return MessageResponse(message="Email successfully verified")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_limit_resend)],
)
async def resend_verification(
    body: ResendVerificationRequest,
    service: RegistrationService = Depends(get_registration_service),
) -> MessageResponse:
    await service.resend_verification(str(body.email))
    return MessageResponse(
        message="If verification is available, an email will be sent"
    )
