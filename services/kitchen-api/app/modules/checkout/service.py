from collections.abc import Callable
from uuid import UUID

from app.infrastructure.unit_of_work import UnitOfWork
from app.modules.cart.service import CartService
from app.modules.checkout.schemas import CheckoutRequest, CheckoutResponse
from app.modules.orders.schemas import CreateOrderRequest, OrderItemRequest
from app.modules.orders.service import OrderService


class CheckoutService:
    def __init__(
        self,
        cart_service: CartService,
        order_service: OrderService,
        uow_factory,
    ):
        self.cart_service = cart_service
        self.order_service = order_service
        self.uow_factory = uow_factory

    async def checkout(
        self,
        user_email: str,
        branch_id: UUID,
        request: CheckoutRequest,
        uow_factory: Callable[[], UnitOfWork] | None = None,
    ) -> CheckoutResponse:
        uow_factory = uow_factory or self.uow_factory
        async with uow_factory() as uow:
            user = await uow.users.users.get_by_email(user_email)
            if user is None:
                return CheckoutResponse(
                    accepted=False, reason="Cart not found"
                )
            branch = await uow.catalog.restaurant_branches.get_by_id(branch_id)
            if branch is None:
                return CheckoutResponse(
                    accepted=False, reason="Branch not found"
                )
            if not branch.is_active or not branch.is_accepting_orders:
                return CheckoutResponse(
                    accepted=False, reason="Branch is unavailable"
                )
            restaurant = await uow.catalog.restaurants.get_by_id(
                branch.restaurant_id
            )
            cart = await uow.cart.carts.get_by_user_and_branch_for_update(
                user.id, branch_id
            )
            if cart is None or not cart.items:
                existing = await uow.orders.orders.get_by_external_id(
                    restaurant.id, request.order_id
                )
                if existing is not None:
                    OrderService.ensure_owner(existing, user.id)
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
            order_items = []
            for item in cart.items:
                relation = await uow.catalog.branch_menu_items.get_by_branch_and_menu_item(
                    branch_id, item.menu_item_id
                )
                if (
                    relation is None
                    or not relation.is_available
                    or relation.price is None
                    or not item.menu_item.is_active
                ):
                    return CheckoutResponse(
                        accepted=False,
                        reason="Menu item is unavailable",
                    )
                order_items.append(
                    OrderItemRequest(
                        menu_item_external_id=item.menu_item.external_id,
                        quantity=item.quantity,
                        unit_price=relation.price,
                    )
                )
            order_request = CreateOrderRequest(
                order_id=request.order_id,
                restaurant_external_id=restaurant.external_id,
                branch_external_id=branch.external_id,
                items=order_items,
            )

        result = await self.order_service.create_order(
            uow_factory=uow_factory,
            request=order_request,
            user_email=user_email,
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
            user = await uow.users.users.get_by_email(user_email)
            await self.cart_service.remove_ordered_quantities(
                uow, user.id, branch_id, ordered_quantities
            )

        return CheckoutResponse(
            accepted=True,
            order_id=result.order_id,
            restaurant_order_id=result.restaurant_order_id,
        )
