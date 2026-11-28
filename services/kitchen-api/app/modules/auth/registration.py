import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import NoReturn
from uuid import UUID

from argon2.exceptions import HashingError, InvalidHashError, VerificationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.security.action_tokens import (
    generate_action_token,
    hash_action_token,
)
from app.core.security.email import normalize_email
from app.core.security.passwords import hash_password, verify_password
from app.infrastructure.clients.email import EmailClient, EmailDeliveryError
from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.auth.errors import (
    AuthTechnicalError,
    InvalidVerificationError,
)
from app.modules.auth.models.user_action_token import (
    TokenPurpose,
    UserActionToken,
)
from app.modules.users.models.user import User
from app.modules.users.service import UserService

UowFactory = Callable[[], UnitOfWork]

EMAIL_TOKEN_TTL = timedelta(hours=24)
TOKEN_MINIMUM_INTERVAL = timedelta(seconds=60)
TOKEN_HOURLY_LIMIT = 5

logger = logging.getLogger(__name__)


class RegistrationService:
    def __init__(
        self,
        email_client: EmailClient,
        uow_factory: UowFactory,
        user_service: UserService,
    ) -> None:
        self.email_client = email_client
        self.uow_factory = uow_factory
        self.user_service = user_service

    async def register(
        self,
        email: str,
        password: str,
    ) -> None:
        email = normalize_email(email)
        try:
            password_hash = await hash_password(password)
        except HashingError as exc:
            self._raise_argon_error("register", "hash", exc)
        raw_token: str | None = None

        try:
            async with self.uow_factory() as uow:
                await uow.users.users.lock_email(email)
                if await uow.users.users.get_by_email(email) is not None:
                    return
                now = datetime.now(timezone.utc)
                raw_token = generate_action_token()
                user = self.user_service.create_pending_user(
                    uow, email, password_hash
                )
                await uow.flush()
                uow.auth.user_action_tokens.add(
                    self._new_email_token(user.id, raw_token, now)
                )
        except IntegrityError as exc:
            if self._is_email_unique_violation(exc):
                return
            self._raise_database_error("register", exc)
        except SQLAlchemyError as exc:
            self._raise_database_error("register", exc)

        if raw_token is not None:
            await self._send_verification_email(email, raw_token)

    async def verify_email(
        self,
        raw_token: str,
        password: str,
    ) -> None:
        token_hash = hash_action_token(raw_token)
        now = datetime.now(timezone.utc)
        try:
            async with self.uow_factory() as uow:
                token = await uow.auth.user_action_tokens.get_by_hash(
                    token_hash
                )
                if not self._token_is_usable(token, now):
                    raise self._invalid_verification()
                user = await uow.users.users.get_by_id(token.user_id)
                if not self._user_can_verify(user):
                    raise self._invalid_verification()
                checked_password_hash = user.password_hash
                user_id = user.id
        except SQLAlchemyError as exc:
            self._raise_database_error("verify_email_initial_read", exc)

        try:
            password_matches = await verify_password(
                password, checked_password_hash
            )
        except (InvalidHashError, VerificationError) as exc:
            self._raise_argon_error("verify_email", "verify", exc)
        if not password_matches:
            raise self._invalid_verification()

        try:
            async with self.uow_factory() as uow:
                user = await uow.users.users.get_by_id_for_update(user_id)
                token = (
                    await uow.auth.user_action_tokens.get_by_hash_for_update(
                        token_hash
                    )
                )
                now = datetime.now(timezone.utc)
                if (
                    not self._user_can_verify(user)
                    or user.password_hash != checked_password_hash
                    or not self._token_is_usable(token, now)
                    or token.user_id != user.id
                ):
                    raise self._invalid_verification()
                self.user_service.mark_email_verified(uow, user, now)
                token.used_at = now
                await uow.auth.user_action_tokens.revoke_active(
                    user.id,
                    TokenPurpose.EMAIL_VERIFICATION.value,
                    now,
                    exclude_id=token.id,
                )
        except SQLAlchemyError as exc:
            self._raise_database_error("verify_email_finalize", exc)

    async def resend_verification(
        self,
        email: str,
    ) -> None:
        email = normalize_email(email)
        raw_token: str | None = None
        try:
            async with self.uow_factory() as uow:
                user = await uow.users.users.get_by_email_for_update(email)
                if not self._user_can_verify(user):
                    return
                now = datetime.now(timezone.utc)
                purpose = TokenPurpose.EMAIL_VERIFICATION.value
                latest = await uow.auth.user_action_tokens.latest_created_at(
                    user.id, purpose
                )
                if (
                    latest is not None
                    and now - latest < TOKEN_MINIMUM_INTERVAL
                ):
                    return
                issued = await uow.auth.user_action_tokens.count_created_since(
                    user.id, purpose, now - timedelta(hours=1)
                )
                if issued >= TOKEN_HOURLY_LIMIT:
                    return
                await uow.auth.user_action_tokens.revoke_active(
                    user.id, purpose, now
                )
                raw_token = generate_action_token()
                uow.auth.user_action_tokens.add(
                    self._new_email_token(user.id, raw_token, now)
                )
        except SQLAlchemyError as exc:
            self._raise_database_error("resend_verification", exc)

        if raw_token is not None:
            await self._send_verification_email(email, raw_token)

    async def _send_verification_email(
        self, email: str, raw_token: str
    ) -> None:
        try:
            await self.email_client.send_verification_email(email, raw_token)
        except EmailDeliveryError:
            logger.warning("Verification email delivery failed after commit")

    @staticmethod
    def _new_email_token(
        user_id: UUID,
        raw_token: str,
        now: datetime,
    ) -> UserActionToken:
        return UserActionToken(
            user_id=user_id,
            token_hash=hash_action_token(raw_token),
            purpose=TokenPurpose.EMAIL_VERIFICATION.value,
            expires_at=now + EMAIL_TOKEN_TTL,
            created_at=now,
        )

    @staticmethod
    def _token_is_usable(token: UserActionToken | None, now: datetime) -> bool:
        return bool(
            token is not None
            and token.purpose == TokenPurpose.EMAIL_VERIFICATION.value
            and token.expires_at > now
            and token.used_at is None
            and token.revoked_at is None
        )

    @staticmethod
    def _user_can_verify(user: User | None) -> bool:
        return bool(
            user is not None
            and user.is_active
            and user.email_verified_at is None
        )

    @staticmethod
    def _invalid_verification() -> InvalidVerificationError:
        return InvalidVerificationError("Invalid verification credentials")

    @staticmethod
    def _postgres_error_details(
        exc: SQLAlchemyError,
    ) -> tuple[str | None, str | None, str]:
        original = getattr(exc, "orig", None)
        driver_error = getattr(original, "__cause__", None)
        sqlstate = getattr(driver_error, "sqlstate", None) or getattr(
            original, "sqlstate", None
        )
        constraint = getattr(driver_error, "constraint_name", None)
        error_type = type(driver_error or original or exc).__name__
        return sqlstate, constraint, error_type

    @classmethod
    def _is_email_unique_violation(cls, exc: IntegrityError) -> bool:
        sqlstate, constraint, _ = cls._postgres_error_details(exc)
        return sqlstate == "23505" and constraint == "users_email_key"

    @classmethod
    def _raise_database_error(
        cls, operation: str, exc: SQLAlchemyError
    ) -> NoReturn:
        sqlstate, constraint, error_type = cls._postgres_error_details(exc)
        logger.error(
            "Auth technical failure component=database operation=%s "
            "error_type=%s error_code=%s constraint=%s",
            operation,
            error_type,
            sqlstate or "unknown",
            constraint or "unknown",
        )
        raise AuthTechnicalError("Authentication operation failed") from None

    @staticmethod
    def _raise_argon_error(
        operation: str, component_operation: str, exc: Exception
    ) -> NoReturn:
        logger.error(
            "Auth technical failure component=argon2 operation=%s.%s "
            "error_type=%s error_code=argon2_failure",
            operation,
            component_operation,
            type(exc).__name__,
        )
        raise AuthTechnicalError("Authentication operation failed") from None
