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
from app.services.order import OrderService


class CartService:
    async def get_cart(
        self,
        uow: UnitOfWork,
        customer_id: UUID,
        branch_id: UUID,
    ) -> CartResponse:
        cart = await self._get_or_create_cart(
            uow=uow,
            customer_id=customer_id,
            branch_id=branch_id,
        )

        return self._to_response(cart)

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
            raise ValueError("Menu item not found")

        branch_item = await uow.branch_menu_items.get_by_branch_and_menu_item(
            branch_id=branch_id,
            menu_item_id=menu_item.id,
        )

        if branch_item is None:
            raise ValueError("Menu item is not available in this branch")

        if not menu_item.is_active or not branch_item.is_available:
            raise ValueError("Menu item is unavailable")

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

        return self._to_response(cart)

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
            raise ValueError("Cart item not found")

        item.quantity = request.quantity

        return self._to_response(cart)

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
            raise ValueError("Cart item not found")

        cart.items.remove(item)

        return self._to_response(cart)

    async def _get_or_create_cart(
        self,
        uow: UnitOfWork,
        customer_id: UUID,
        branch_id: UUID,
    ) -> Cart:
        branch = await uow.restaurant_branches.get_by_id(branch_id)

        if branch is None:
            raise ValueError("Branch not found")

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
            raise ValueError("Cart not found")

        return cart

    @staticmethod
    def _to_response(cart: Cart) -> CartResponse:
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
                    is_available=True,
                )
                for item in cart.items
            ],
        )

    async def checkout(
        self,
        uow: UnitOfWork,
        customer_id: UUID,
        customer_email: str,
        branch_id: UUID,
        request: CheckoutRequest,
    ) -> CheckoutResponse:
        cart = await self._get_cart(
            uow=uow,
            customer_id=customer_id,
            branch_id=branch_id,
        )

        if not cart.items:
            return CheckoutResponse(
                accepted=False,
                reason="Cart is empty",
            )

        branch = await uow.restaurant_branches.get_by_id(branch_id)

        if branch is None:
            return CheckoutResponse(
                accepted=False,
                reason="Branch not found",
            )

        if not branch.is_active or not branch.is_accepting_orders:
            return CheckoutResponse(
                accepted=False,
                reason="Branch is unavailable",
            )

        order_request = CreateOrderRequest(
            order_id=request.order_id,
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
            uow=uow,
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

        cart.items.clear()

        return CheckoutResponse(
            accepted=True,
            order_id=result.order_id,
            restaurant_order_id=result.restaurant_order_id,
        )
