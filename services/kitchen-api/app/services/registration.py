import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from argon2.exceptions import InvalidHashError
from sqlalchemy.exc import IntegrityError

from app.core.security.action_tokens import (
    generate_action_token,
    hash_action_token,
)
from app.core.security.email import normalize_email
from app.core.security.passwords import hash_password, verify_password
from app.infrastructure.clients.email import EmailClient, EmailDeliveryError
from app.infrastructure.database.models.user import User, UserRole
from app.infrastructure.database.models.user_action_token import (
    TokenPurpose,
    UserActionToken,
)
from app.infrastructure.unit_of_work import UnitOfWork
from app.services.errors import InvalidVerificationError

UowFactory = Callable[[], UnitOfWork]

EMAIL_TOKEN_TTL = timedelta(hours=24)
TOKEN_MINIMUM_INTERVAL = timedelta(seconds=60)
TOKEN_HOURLY_LIMIT = 5

logger = logging.getLogger(__name__)


class RegistrationService:
    def __init__(self, email_client: EmailClient) -> None:
        self.email_client = email_client

    async def register(
        self,
        uow_factory: UowFactory,
        email: str,
        password: str,
    ) -> None:
        email = normalize_email(email)
        password_hash = await hash_password(password)
        raw_token = generate_action_token()
        now = datetime.now(timezone.utc)
        created = False

        try:
            async with uow_factory() as uow:
                await uow.users.lock_email(email)
                if await uow.users.get_by_email(email) is not None:
                    return
                user = uow.users.add(
                    User(
                        email=email,
                        password_hash=password_hash,
                        role=UserRole.CUSTOMER.value,
                        is_active=True,
                        email_verified_at=None,
                    )
                )
                await uow.flush()
                uow.user_action_tokens.add(
                    self._new_email_token(user.id, raw_token, now)
                )
                created = True
        except IntegrityError:
            return

        if created:
            await self._send_verification_email(email, raw_token)

    async def verify_email(
        self,
        uow_factory: UowFactory,
        raw_token: str,
        password: str,
    ) -> None:
        token_hash = hash_action_token(raw_token)
        now = datetime.now(timezone.utc)
        async with uow_factory() as uow:
            token = await uow.user_action_tokens.get_by_hash(token_hash)
            if not self._token_is_usable(token, now):
                raise self._invalid_verification()
            user = await uow.users.get_by_id(token.user_id)
            if not self._user_can_verify(user):
                raise self._invalid_verification()
            checked_password_hash = user.password_hash
            user_id = user.id

        try:
            password_matches = await verify_password(
                password, checked_password_hash
            )
        except InvalidHashError:
            raise self._invalid_verification() from None
        if not password_matches:
            raise self._invalid_verification()

        now = datetime.now(timezone.utc)
        async with uow_factory() as uow:
            user = await uow.users.get_by_id_for_update(user_id)
            if (
                not self._user_can_verify(user)
                or user.password_hash != checked_password_hash
            ):
                raise self._invalid_verification()
            token = await uow.user_action_tokens.get_by_hash_for_update(
                token_hash
            )
            if (
                not self._token_is_usable(token, now)
                or token.user_id != user.id
            ):
                raise self._invalid_verification()
            user.email_verified_at = now
            token.used_at = now
            await uow.user_action_tokens.revoke_active(
                user.id,
                TokenPurpose.EMAIL_VERIFICATION.value,
                now,
                exclude_id=token.id,
            )

    async def resend_verification(
        self,
        uow_factory: UowFactory,
        email: str,
    ) -> None:
        email = normalize_email(email)
        raw_token: str | None = None
        async with uow_factory() as uow:
            candidate = await uow.users.get_by_email(email)
            if candidate is None:
                return
            user = await uow.users.get_by_id_for_update(candidate.id)
            if not self._user_can_verify(user):
                return
            now = datetime.now(timezone.utc)
            purpose = TokenPurpose.EMAIL_VERIFICATION.value
            latest = await uow.user_action_tokens.latest_created_at(
                user.id, purpose
            )
            if latest is not None and now - latest < TOKEN_MINIMUM_INTERVAL:
                return
            issued = await uow.user_action_tokens.count_created_since(
                user.id, purpose, now - timedelta(hours=1)
            )
            if issued >= TOKEN_HOURLY_LIMIT:
                return
            await uow.user_action_tokens.revoke_active(user.id, purpose, now)
            raw_token = generate_action_token()
            uow.user_action_tokens.add(
                self._new_email_token(user.id, raw_token, now)
            )

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
        user_id,
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
