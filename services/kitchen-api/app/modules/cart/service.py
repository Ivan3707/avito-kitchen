from uuid import UUID, uuid4

from app.core.errors import ConflictError, ResourceNotFoundError
from app.infrastructure.unit_of_work import UnitOfWork, UowFactory
from app.modules.cart.models.cart import Cart
from app.modules.cart.models.cart_item import CartItem
from app.modules.cart.schemas import (
    AddCartItemRequest,
    CartItemResponse,
    CartResponse,
    UpdateCartItemRequest,
)


class CartService:
    def __init__(self, uow_factory: UowFactory) -> None:
        self.uow_factory = uow_factory

    async def get_cart_by_email(
        self, user_email: str, branch_id: UUID
    ) -> CartResponse:
        async with self.uow_factory() as uow:
            user = await uow.users.users.get_by_email(user_email)
            if user is None:
                return CartResponse(id=None, branch_id=branch_id, items=[])
            return await self.get_cart(uow, user.id, branch_id)

    async def add_item_by_email(
        self, user_email: str, branch_id: UUID, request: AddCartItemRequest
    ) -> CartResponse:
        async with self.uow_factory() as uow:
            user = await uow.users.users.get_by_email(user_email)
            if user is None:
                raise ResourceNotFoundError("User not found")
            return await self.add_item(uow, user.id, branch_id, request)

    async def update_item_by_email(
        self,
        user_email: str,
        branch_id: UUID,
        menu_item_id: UUID,
        request: UpdateCartItemRequest,
    ) -> CartResponse:
        async with self.uow_factory() as uow:
            user = await uow.users.users.get_by_email(user_email)
            if user is None:
                raise ResourceNotFoundError("User not found")
            return await self.update_item(
                uow, user.id, branch_id, menu_item_id, request
            )

    async def remove_item_by_email(
        self, user_email: str, branch_id: UUID, menu_item_id: UUID
    ) -> CartResponse:
        async with self.uow_factory() as uow:
            user = await uow.users.users.get_by_email(user_email)
            if user is None:
                raise ResourceNotFoundError("User not found")
            return await self.remove_item(
                uow, user.id, branch_id, menu_item_id
            )

    async def remove_ordered_quantities(
        self,
        uow: UnitOfWork,
        user_id: UUID,
        branch_id: UUID,
        ordered_quantities: dict[UUID, int],
    ) -> None:
        cart = await uow.cart.carts.get_by_user_and_branch_for_update(
            user_id, branch_id
        )
        for item in list(cart.items):
            ordered = ordered_quantities.get(item.menu_item_id, 0)
            if ordered == 0:
                continue
            if item.quantity <= ordered:
                cart.items.remove(item)
            else:
                item.quantity -= ordered

    async def get_cart(
        self,
        uow: UnitOfWork,
        user_id: UUID,
        branch_id: UUID,
    ) -> CartResponse:
        cart = await uow.cart.carts.get_by_user_and_branch(
            user_id=user_id,
            branch_id=branch_id,
        )
        if cart is None:
            return CartResponse(id=None, branch_id=branch_id, items=[])
        return await self._to_response(uow, cart)

    async def add_item(
        self,
        uow: UnitOfWork,
        user_id: UUID,
        branch_id: UUID,
        request: AddCartItemRequest,
    ) -> CartResponse:
        cart = await self._get_or_create_cart(
            uow=uow,
            user_id=user_id,
            branch_id=branch_id,
        )

        menu_item = await uow.catalog.menu_items.get_by_id(
            request.menu_item_id
        )

        if menu_item is None:
            raise ResourceNotFoundError("Menu item not found")

        branch_item = (
            await uow.catalog.branch_menu_items.get_by_branch_and_menu_item(
                branch_id=branch_id,
                menu_item_id=menu_item.id,
            )
        )

        if branch_item is None:
            raise ConflictError("Menu item is not available in this branch")

        if (
            not menu_item.is_active
            or not branch_item.is_available
            or branch_item.price is None
        ):
            raise ConflictError("Menu item is unavailable")

        existing_item = next(
            (item for item in cart.items if item.menu_item_id == menu_item.id),
            None,
        )

        if existing_item is not None:
            existing_item.quantity += request.quantity
        else:
            cart.items.append(
                CartItem(
                    menu_item=menu_item,
                    quantity=request.quantity,
                )
            )

        return await self._to_response(uow, cart)

    async def update_item(
        self,
        uow: UnitOfWork,
        user_id: UUID,
        branch_id: UUID,
        menu_item_id: UUID,
        request: UpdateCartItemRequest,
    ) -> CartResponse:
        cart = await self._get_cart(
            uow=uow,
            user_id=user_id,
            branch_id=branch_id,
        )

        item = next(
            (item for item in cart.items if item.menu_item_id == menu_item_id),
            None,
        )

        if item is None:
            raise ResourceNotFoundError("Cart item not found")

        item.quantity = request.quantity

        return await self._to_response(uow, cart)

    async def remove_item(
        self,
        uow: UnitOfWork,
        user_id: UUID,
        branch_id: UUID,
        menu_item_id: UUID,
    ) -> CartResponse:
        cart = await self._get_cart(
            uow=uow,
            user_id=user_id,
            branch_id=branch_id,
        )

        item = next(
            (item for item in cart.items if item.menu_item_id == menu_item_id),
            None,
        )

        if item is None:
            raise ResourceNotFoundError("Cart item not found")

        cart.items.remove(item)

        return await self._to_response(uow, cart)

    async def _get_or_create_cart(
        self,
        uow: UnitOfWork,
        user_id: UUID,
        branch_id: UUID,
    ) -> Cart:
        branch = await uow.catalog.restaurant_branches.get_by_id(branch_id)

        if branch is None:
            raise ResourceNotFoundError("Branch not found")

        await uow.cart.carts.lock_user_branch(user_id, branch_id)
        cart = await uow.cart.carts.get_by_user_and_branch(
            user_id=user_id,
            branch_id=branch_id,
        )

        if cart is not None:
            return cart

        return uow.cart.carts.add(
            Cart(
                id=uuid4(),
                user_id=user_id,
                branch_id=branch_id,
                items=[],
            )
        )

    async def _get_cart(
        self,
        uow: UnitOfWork,
        user_id: UUID,
        branch_id: UUID,
    ) -> Cart:
        cart = await uow.cart.carts.get_by_user_and_branch(
            user_id=user_id,
            branch_id=branch_id,
        )

        if cart is None:
            raise ResourceNotFoundError("Cart not found")

        return cart

    @staticmethod
    async def _to_response(uow: UnitOfWork, cart: Cart) -> CartResponse:
        branch_items = {}
        for item in cart.items:
            relation = await uow.catalog.branch_menu_items.get_by_branch_and_menu_item(
                cart.branch_id, item.menu_item_id
            )
            branch_items[item.menu_item_id] = relation
        return CartResponse(
            id=cart.id,
            branch_id=cart.branch_id,
            items=[
                CartItemResponse(
                    menu_item_id=item.menu_item.id,
                    menu_item_external_id=item.menu_item.external_id,
                    name=item.menu_item.name,
                    price=(
                        branch_items[item.menu_item_id].price
                        if branch_items[item.menu_item_id] is not None
                        else None
                    ),
                    quantity=item.quantity,
                    is_available=bool(
                        branch_items[item.menu_item_id]
                        and branch_items[item.menu_item_id].is_available
                        and branch_items[item.menu_item_id].price is not None
                        and item.menu_item.is_active
                    ),
                )
                for item in cart.items
            ],
        )
