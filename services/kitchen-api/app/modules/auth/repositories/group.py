from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.repositories.user_action_token import (
    UserActionTokenRepository,
)


class AuthRepositories:
    def __init__(self, session: AsyncSession):
        self.user_action_tokens = UserActionTokenRepository(session)
