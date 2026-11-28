from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cart.repositories.cart import CartRepository


class CartRepositories:
    def __init__(self, session: AsyncSession):
        self.carts = CartRepository(session)
