from collections.abc import Callable
from uuid import UUID, uuid4

from app.core.config import settings
from app.infrastructure.clients.restaurant import RestaurantClient
from app.infrastructure.database.models.cart import Cart
from app.infrastructure.database.models.cart_item import CartItem
from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.cart import (
    AddCartItemRequest,
    CartItemResponse,
    CartResponse,
    CheckoutRequest,
    CheckoutResponse,
    UpdateCartItemRequest,
)
from app.integration.schemas.orders import (
    CreateOrderRequest,
    OrderItemRequest,
)
from app.services.errors import ConflictError, ResourceNotFoundError
from app.services.order import OrderService


class CartService:
    async def get_cart(
        self,
        uow: UnitOfWork,
        customer_id: UUID,
        branch_id: UUID,
    ) -> CartResponse:
        cart = await uow.carts.get_by_customer_and_branch(
            customer_id=customer_id,
            branch_id=branch_id,
        )
        if cart is None:
            return CartResponse(id=None, branch_id=branch_id, items=[])
        return await self._to_response(uow, cart)

    async def add_item(
        self,
        uow: UnitOfWork,
        customer_id: UUID,
        branch_id: UUID,
        request: AddCartItemRequest,
    ) -> CartResponse:
        cart = await self._get_or_create_cart(
            uow=uow,
            customer_id=customer_id,
            branch_id=branch_id,
        )

        menu_item = await uow.menu_items.get_by_id(request.menu_item_id)

        if menu_item is None:
            raise ResourceNotFoundError("Menu item not found")

        branch_item = await uow.branch_menu_items.get_by_branch_and_menu_item(
            branch_id=branch_id,
            menu_item_id=menu_item.id,
        )

        if branch_item is None:
            raise ConflictError("Menu item is not available in this branch")

        if not menu_item.is_active or not branch_item.is_available:
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
        customer_id: UUID,
        branch_id: UUID,
        menu_item_id: UUID,
        request: UpdateCartItemRequest,
    ) -> CartResponse:
        cart = await self._get_cart(
            uow=uow,
            customer_id=customer_id,
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
        customer_id: UUID,
        branch_id: UUID,
        menu_item_id: UUID,
    ) -> CartResponse:
        cart = await self._get_cart(
            uow=uow,
            customer_id=customer_id,
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
        customer_id: UUID,
        branch_id: UUID,
    ) -> Cart:
        branch = await uow.restaurant_branches.get_by_id(branch_id)

        if branch is None:
            raise ResourceNotFoundError("Branch not found")

        cart = await uow.carts.get_by_customer_and_branch(
            customer_id=customer_id,
            branch_id=branch_id,
        )

        if cart is not None:
            return cart

        return uow.carts.add(
            Cart(
                id=uuid4(),
                customer_id=customer_id,
                branch_id=branch_id,
            )
        )

    async def _get_cart(
        self,
        uow: UnitOfWork,
        customer_id: UUID,
        branch_id: UUID,
    ) -> Cart:
        cart = await uow.carts.get_by_customer_and_branch(
            customer_id=customer_id,
            branch_id=branch_id,
        )

        if cart is None:
            raise ResourceNotFoundError("Cart not found")

        return cart

    @staticmethod
    async def _to_response(uow: UnitOfWork, cart: Cart) -> CartResponse:
        availability = {}
        for item in cart.items:
            relation = await uow.branch_menu_items.get_by_branch_and_menu_item(
                cart.branch_id, item.menu_item_id
            )
            availability[item.menu_item_id] = bool(
                relation and relation.is_available and item.menu_item.is_active
            )
        return CartResponse(
            id=cart.id,
            branch_id=cart.branch_id,
            items=[
                CartItemResponse(
                    menu_item_id=item.menu_item.id,
                    menu_item_external_id=item.menu_item.external_id,
                    name=item.menu_item.name,
                    price=item.menu_item.price,
                    quantity=item.quantity,
                    is_available=availability[item.menu_item_id],
                )
                for item in cart.items
            ],
        )

    async def checkout(
        self,
        uow_factory: Callable[[], UnitOfWork],
        customer_email: str,
        branch_id: UUID,
        request: CheckoutRequest,
    ) -> CheckoutResponse:
        async with uow_factory() as uow:
            customer = await uow.customers.get_by_email(customer_email)
            if customer is None:
                return CheckoutResponse(
                    accepted=False, reason="Cart not found"
                )
            branch = await uow.restaurant_branches.get_by_id(branch_id)
            if branch is None:
                return CheckoutResponse(
                    accepted=False, reason="Branch not found"
                )
            if not branch.is_active or not branch.is_accepting_orders:
                return CheckoutResponse(
                    accepted=False, reason="Branch is unavailable"
                )
            restaurant = await uow.restaurants.get_by_id(branch.restaurant_id)
            cart = await uow.carts.get_by_customer_and_branch_for_update(
                customer.id, branch_id
            )
            if cart is None or not cart.items:
                existing = await uow.orders.get_by_external_id(
                    restaurant.id, request.order_id
                )
                if existing is not None and existing.status != "pending":
                    stored = OrderService.stored_response(existing)
                    return CheckoutResponse(
                        accepted=stored.accepted,
                        order_id=stored.order_id,
                        restaurant_order_id=stored.restaurant_order_id,
                        reason=(
                            stored.reason.message
                            if stored.reason is not None
                            else None
                        ),
                    )
                return CheckoutResponse(accepted=False, reason="Cart is empty")
            ordered_quantities = {
                item.menu_item_id: item.quantity for item in cart.items
            }
            order_request = CreateOrderRequest(
                order_id=request.order_id,
                restaurant_external_id=restaurant.external_id,
                branch_external_id=branch.external_id,
                items=[
                    OrderItemRequest(
                        menu_item_external_id=item.menu_item.external_id,
                        quantity=item.quantity,
                        unit_price=item.menu_item.price,
                    )
                    for item in cart.items
                ],
            )

        restaurant_client = RestaurantClient(
            settings.DEMO_RESTAURANT_URL,
        )

        order_service = OrderService()

        result = await order_service.create_order(
            uow_factory=uow_factory,
            request=order_request,
            customer_email=customer_email,
            restaurant_client=restaurant_client,
        )

        if not result.accepted:
            return CheckoutResponse(
                accepted=False,
                reason=(
                    result.reason.message
                    if result.reason is not None
                    else "Restaurant rejected the order"
                ),
            )

        async with uow_factory() as uow:
            customer = await uow.customers.get_by_email(customer_email)
            cart = await uow.carts.get_by_customer_and_branch_for_update(
                customer.id, branch_id
            )
            for item in list(cart.items):
                ordered = ordered_quantities.get(item.menu_item_id, 0)
                if ordered == 0:
                    continue
                if item.quantity <= ordered:
                    cart.items.remove(item)
                else:
                    item.quantity -= ordered

        return CheckoutResponse(
            accepted=True,
            order_id=result.order_id,
            restaurant_order_id=result.restaurant_order_id,
        )
