from hashlib import sha256

from app.infrastructure.clients.restaurant import (
    RestaurantClient,
    RestaurantTimeoutError,
)
from app.infrastructure.database.models.customer import Customer
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


class OrderService:
    async def validate_order(
        self,
        uow: UnitOfWork,
        request: OrderValidationRequest,
    ) -> OrderValidationResponse:
        branch = (
            await uow.restaurant_branches.get_by_external_id_any_restaurant(
                request.branch_external_id,
            )
        )

        if (
            branch is None
            or not branch.is_active
            or not branch.is_accepting_orders
        ):
            return OrderValidationResponse(
                valid=False,
                issues=[
                    ValidationIssue(
                        code=BusinessErrorCode.BRANCH_UNAVAILABLE,
                        message="Branch is unavailable",
                    )
                ],
            )

        menu = await uow.menus.get_by_restaurant_id(
            branch.restaurant_id,
        )

        if menu is None:
            return OrderValidationResponse(
                valid=False,
                issues=[
                    ValidationIssue(
                        code=BusinessErrorCode.PRODUCT_NOT_FOUND,
                        message="Restaurant menu not found",
                    )
                ],
            )

        issues: list[ValidationIssue] = []

        for requested_item in request.items:
            menu_item = await uow.menu_items.get_by_menu_and_external_id(
                menu.id,
                requested_item.menu_item_external_id,
            )

            if menu_item is None:
                issues.append(
                    ValidationIssue(
                        code=BusinessErrorCode.PRODUCT_NOT_FOUND,
                        message="Product not found",
                        menu_item_external_id=(
                            requested_item.menu_item_external_id
                        ),
                    )
                )
                continue

            if not menu_item.is_active:
                issues.append(
                    ValidationIssue(
                        code=BusinessErrorCode.PRODUCT_UNAVAILABLE,
                        message="Product is unavailable",
                        menu_item_external_id=(
                            requested_item.menu_item_external_id
                        ),
                    )
                )
                continue

            branch_menu_item = (
                await uow.branch_menu_items.get_by_branch_and_menu_item(
                    branch.id,
                    menu_item.id,
                )
            )

            if branch_menu_item is None or not branch_menu_item.is_available:
                issues.append(
                    ValidationIssue(
                        code=BusinessErrorCode.PRODUCT_UNAVAILABLE,
                        message="Product is unavailable in this branch",
                        menu_item_external_id=(
                            requested_item.menu_item_external_id
                        ),
                    )
                )
                continue

            if menu_item.price != requested_item.unit_price:
                issues.append(
                    ValidationIssue(
                        code=BusinessErrorCode.PRICE_CHANGED,
                        message="Product price has changed",
                        menu_item_external_id=(
                            requested_item.menu_item_external_id
                        ),
                        old_price=requested_item.unit_price,
                        current_price=menu_item.price,
                    )
                )

        return OrderValidationResponse(
            valid=not issues,
            issues=issues,
        )

    async def create_order(
        self,
        uow: UnitOfWork,
        request: CreateOrderRequest,
        customer_email: str,
        restaurant_client: RestaurantClient | None = None,
    ) -> CreateOrderResponse:
        branch = (
            await uow.restaurant_branches.get_by_external_id_any_restaurant(
                request.branch_external_id,
            )
        )

        if branch is None:
            return self._rejected(
                BusinessErrorCode.BRANCH_UNAVAILABLE,
                "Branch is unavailable",
            )

        request_hash = self._calculate_request_hash(request)

        # Idempotency check must happen before current catalog validation.
        # A repeated request for an already-created order must return
        # the existing result even if the catalog has changed since then.
        existing_order = await uow.orders.get_by_external_id(
            branch.restaurant_id,
            request.order_id,
        )

        if existing_order is not None:
            if existing_order.request_hash != request_hash:
                return self._rejected(
                    BusinessErrorCode.ORDER_ID_CONFLICT,
                    "Order ID was already used for another request",
                )

            return CreateOrderResponse(
                accepted=True,
                order_id=existing_order.id,
                restaurant_order_id=existing_order.restaurant_order_id,
            )

        # The order does not exist yet, so this is a new request.
        validation = await self.validate_order(
            uow=uow,
            request=OrderValidationRequest(
                branch_external_id=request.branch_external_id,
                items=request.items,
            ),
        )

        if not validation.valid:
            return CreateOrderResponse(
                accepted=False,
                reason=validation.issues[0],
            )

        customer = await uow.customers.get_by_email(customer_email)

        if customer is None:
            customer = uow.customers.add(Customer(email=customer_email))
            await uow.session.flush()

        if restaurant_client is None:
            return self._rejected(
                BusinessErrorCode.BRANCH_UNAVAILABLE,
                "Restaurant client is not configured",
            )

        try:
            restaurant_response = await restaurant_client.create_order(
                {
                    "order_id": request.order_id,
                    "branch_external_id": request.branch_external_id,
                    "items": [
                        {
                            "menu_item_external_id": item.menu_item_external_id,
                            "quantity": item.quantity,
                            "unit_price": item.unit_price,
                        }
                        for item in request.items
                    ],
                }
            )

        except RestaurantTimeoutError:
            return self._rejected(
                BusinessErrorCode.RESTAURANT_TIMEOUT,
                "Restaurant did not respond in time",
            )

        if not restaurant_response.get("accepted"):
            return self._rejected(
                BusinessErrorCode.PRODUCT_UNAVAILABLE,
                restaurant_response.get(
                    "reason",
                    "Restaurant rejected the order",
                ),
            )

        restaurant_order_id = restaurant_response["restaurant_order_id"]

        order = uow.orders.add(
            Order(
                customer_id=customer.id,
                restaurant_id=branch.restaurant_id,
                branch_id=branch.id,
                external_order_id=request.order_id,
                restaurant_order_id=restaurant_order_id,
                request_hash=request_hash,
            )
        )

        await uow.session.flush()

        menu = await uow.menus.get_by_restaurant_id(branch.restaurant_id)

        for requested_item in request.items:
            menu_item = await uow.menu_items.get_by_menu_and_external_id(
                menu.id,
                requested_item.menu_item_external_id,
            )

            uow.session.add(
                OrderItem(
                    order_id=order.id,
                    menu_item_id=menu_item.id,
                    product_name=menu_item.name,
                    unit_price=menu_item.price,
                    quantity=requested_item.quantity,
                )
            )

        return CreateOrderResponse(
            accepted=True,
            order_id=order.id,
            restaurant_order_id=restaurant_order_id,
        )

    @staticmethod
    def _calculate_request_hash(
        request: CreateOrderRequest,
    ) -> str:
        payload = (
            f"{request.order_id}|"
            f"{request.branch_external_id}|"
            + "|".join(
                (
                    f"{item.menu_item_external_id}:"
                    f"{item.quantity}:"
                    f"{item.unit_price}"
                )
                for item in request.items
            )
        )

        return sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _rejected(
        code: BusinessErrorCode,
        message: str,
    ) -> CreateOrderResponse:
        return CreateOrderResponse(
            accepted=False,
            reason=ValidationIssue(
                code=code,
                message=message,
            ),
        )
