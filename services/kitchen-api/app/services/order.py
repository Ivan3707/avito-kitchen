import json
from collections.abc import Callable
from hashlib import sha256

from app.infrastructure.clients.restaurant import (
    RestaurantClient,
    RestaurantCommunicationError,
    RestaurantTimeoutError,
)
from app.infrastructure.database.models.order import Order
from app.infrastructure.database.models.order_item import OrderItem
from app.infrastructure.unit_of_work import UnitOfWork
from app.integration.schemas.common import BusinessErrorCode
from app.integration.schemas.orders import (
    CreateOrderRequest,
    CreateOrderResponse,
    OrderValidationRequest,
    OrderValidationResponse,
    ValidationIssue,
)
from app.services.errors import ResourceNotFoundError

UowFactory = Callable[[], UnitOfWork]


class OrderService:
    async def validate_order(
        self,
        uow: UnitOfWork,
        request: OrderValidationRequest,
    ) -> OrderValidationResponse:
        restaurant = await uow.restaurants.get_by_external_id(
            request.restaurant_external_id
        )
        if restaurant is None:
            return self._invalid_branch()
        branch = (
            await uow.restaurant_branches.get_by_restaurant_and_external_id(
                restaurant.id,
                request.branch_external_id,
            )
        )
        if (
            branch is None
            or not branch.is_active
            or not branch.is_accepting_orders
        ):
            return self._invalid_branch()

        menu = await uow.menus.get_by_restaurant_id(restaurant.id)
        if menu is None:
            return OrderValidationResponse(
                valid=False,
                issues=[
                    ValidationIssue(
                        code=BusinessErrorCode.PRODUCT_NOT_FOUND,
                        message="Restaurant menu not found",
                        menu_item_external_id=request.items[
                            0
                        ].menu_item_external_id,
                    )
                ],
            )

        issues: list[ValidationIssue] = []
        for requested_item in request.items:
            menu_item = await uow.menu_items.get_by_menu_and_external_id(
                menu.id, requested_item.menu_item_external_id
            )
            if menu_item is None:
                issues.append(
                    ValidationIssue(
                        code=BusinessErrorCode.PRODUCT_NOT_FOUND,
                        message="Product not found",
                        menu_item_external_id=requested_item.menu_item_external_id,
                    )
                )
                continue
            if not menu_item.is_active:
                issues.append(
                    ValidationIssue(
                        code=BusinessErrorCode.PRODUCT_UNAVAILABLE,
                        message="Product is unavailable",
                        menu_item_external_id=requested_item.menu_item_external_id,
                    )
                )
                continue
            relation = await uow.branch_menu_items.get_by_branch_and_menu_item(
                branch.id, menu_item.id
            )
            if (
                relation is None
                or not relation.is_available
                or relation.price is None
            ):
                issues.append(
                    ValidationIssue(
                        code=BusinessErrorCode.PRODUCT_UNAVAILABLE,
                        message="Product is unavailable in this branch",
                        menu_item_external_id=requested_item.menu_item_external_id,
                    )
                )
                continue
            if relation.price != requested_item.unit_price:
                issues.append(
                    ValidationIssue(
                        code=BusinessErrorCode.PRICE_CHANGED,
                        message="Product price has changed",
                        menu_item_external_id=requested_item.menu_item_external_id,
                        old_price=requested_item.unit_price,
                        current_price=relation.price,
                    )
                )
        return OrderValidationResponse(valid=not issues, issues=issues)

    async def create_order(
        self,
        uow_factory: UowFactory,
        request: CreateOrderRequest,
        user_email: str,
        restaurant_client: RestaurantClient,
    ) -> CreateOrderResponse:
        request_hash = self._calculate_request_hash(request)
        async with uow_factory() as uow:
            restaurant = await uow.restaurants.get_by_external_id(
                request.restaurant_external_id
            )
            if restaurant is None:
                return self._rejected(
                    BusinessErrorCode.BRANCH_UNAVAILABLE,
                    "Restaurant or branch is unavailable",
                )
            user = await uow.users.get_by_email(user_email)
            if user is None:
                raise ResourceNotFoundError("User not found")
            await uow.orders.lock_external_id(restaurant.id, request.order_id)
            existing = await uow.orders.get_by_external_id_for_update(
                restaurant.id, request.order_id
            )
            if existing is not None:
                if existing.request_hash != request_hash:
                    return self._rejected(
                        BusinessErrorCode.ORDER_ID_CONFLICT,
                        "Order ID was already used for another request",
                    )
                if existing.status != "pending":
                    return self.stored_response(existing)
                local_order_id = existing.id
            else:
                validation = await self.validate_order(
                    uow,
                    OrderValidationRequest(
                        restaurant_external_id=request.restaurant_external_id,
                        branch_external_id=request.branch_external_id,
                        items=request.items,
                    ),
                )
                if not validation.valid:
                    return CreateOrderResponse(
                        accepted=False, reason=validation.issues[0]
                    )
                branch = await uow.restaurant_branches.get_by_restaurant_and_external_id(
                    restaurant.id, request.branch_external_id
                )
                order = uow.orders.add(
                    Order(
                        user_id=user.id,
                        restaurant_id=restaurant.id,
                        branch_id=branch.id,
                        external_order_id=request.order_id,
                        restaurant_order_id=None,
                        request_hash=request_hash,
                        status="pending",
                    )
                )
                await uow.flush()
                menu = await uow.menus.get_by_restaurant_id(restaurant.id)
                for requested_item in request.items:
                    menu_item = (
                        await uow.menu_items.get_by_menu_and_external_id(
                            menu.id, requested_item.menu_item_external_id
                        )
                    )
                    uow.order_items.add(
                        OrderItem(
                            order_id=order.id,
                            menu_item_id=menu_item.id,
                            product_name=menu_item.name,
                            unit_price=requested_item.unit_price,
                            quantity=requested_item.quantity,
                        )
                    )
                local_order_id = order.id

        try:
            restaurant_response = await restaurant_client.create_order(
                {
                    "order_id": request.order_id,
                    "branch_external_id": request.branch_external_id,
                    "items": [
                        item.model_dump(mode="json") for item in request.items
                    ],
                }
            )
        except (RestaurantTimeoutError, RestaurantCommunicationError):
            return self._rejected(
                BusinessErrorCode.RESTAURANT_TIMEOUT,
                "Restaurant result is unknown; retry with the same order_id",
            )

        async with uow_factory() as uow:
            restaurant = await uow.restaurants.get_by_external_id(
                request.restaurant_external_id
            )
            await uow.orders.lock_external_id(restaurant.id, request.order_id)
            order = await uow.orders.get_by_external_id_for_update(
                restaurant.id, request.order_id
            )
            if order.status != "pending":
                return self.stored_response(order)
            if restaurant_response.accepted:
                order.status = "confirmed"
                order.restaurant_order_id = (
                    restaurant_response.restaurant_order_id
                )
            else:
                issue = restaurant_response.reason
                order.status = "rejected"
                order.rejection_code = issue.code.value
                order.rejection_message = issue.message
                order.rejection_menu_item_external_id = (
                    issue.menu_item_external_id
                )
                order.rejection_old_price = issue.old_price
                order.rejection_current_price = issue.current_price
            result = self.stored_response(order)
            result.order_id = local_order_id
            return result

    @staticmethod
    def _invalid_branch() -> OrderValidationResponse:
        return OrderValidationResponse(
            valid=False,
            issues=[
                ValidationIssue(
                    code=BusinessErrorCode.BRANCH_UNAVAILABLE,
                    message="Branch is unavailable",
                )
            ],
        )

    @staticmethod
    def stored_response(order: Order) -> CreateOrderResponse:
        if order.status == "confirmed":
            return CreateOrderResponse(
                accepted=True,
                order_id=order.id,
                restaurant_order_id=order.restaurant_order_id,
            )
        if order.status == "rejected":
            return CreateOrderResponse(
                accepted=False,
                order_id=order.id,
                reason=ValidationIssue(
                    code=BusinessErrorCode(order.rejection_code),
                    message=order.rejection_message,
                    menu_item_external_id=(
                        order.rejection_menu_item_external_id
                    ),
                    old_price=order.rejection_old_price,
                    current_price=order.rejection_current_price,
                ),
            )
        raise RuntimeError("pending order has no final response")

    @staticmethod
    def _calculate_request_hash(request: CreateOrderRequest) -> str:
        canonical = json.dumps(
            request.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _rejected(
        code: BusinessErrorCode, message: str
    ) -> CreateOrderResponse:
        return CreateOrderResponse(
            accepted=False,
            reason=ValidationIssue(code=code, message=message),
        )
