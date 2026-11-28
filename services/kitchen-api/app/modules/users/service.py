from datetime import datetime

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.users.models.user import User, UserRole


class UserService:
    def create_pending_user(
        self, uow: UnitOfWork, email: str, password_hash: str
    ) -> User:
        return uow.users.users.add(
            User(
                email=email,
                password_hash=password_hash,
                role=UserRole.CUSTOMER.value,
                is_active=True,
                email_verified_at=None,
            )
        )

    def mark_email_verified(
        self, uow: UnitOfWork, user: User, now: datetime
    ) -> None:
        user.email_verified_at = now
