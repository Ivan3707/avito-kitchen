from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.infrastructure.database.models.cart import Cart
from app.infrastructure.database.models.cart_item import CartItem
from app.infrastructure.repositories.base import BaseRepository


class CartRepository(BaseRepository[Cart]):
    model = Cart

    async def get_with_items(
        self,
        cart_id: UUID,
    ) -> Cart | None:
        result = await self.session.execute(
            select(self.model)
            .options(selectinload(Cart.items).selectinload(CartItem.menu_item))
            .where(self.model.id == cart_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_and_branch(
        self,
        user_id: UUID,
        branch_id: UUID,
    ) -> Cart | None:
        result = await self.session.execute(
            select(self.model)
            .options(selectinload(Cart.items).selectinload(CartItem.menu_item))
            .where(
                self.model.user_id == user_id,
                self.model.branch_id == branch_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_and_branch_for_update(
        self,
        user_id: UUID,
        branch_id: UUID,
    ) -> Cart | None:
        result = await self.session.execute(
            select(self.model)
            .options(selectinload(Cart.items).selectinload(CartItem.menu_item))
            .where(
                self.model.user_id == user_id,
                self.model.branch_id == branch_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()
