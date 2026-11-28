from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.repositories.user import UserRepository


class UserRepositories:
    def __init__(self, session: AsyncSession):
        self.users = UserRepository(session)
