import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from app.core.config import settings
from app.infrastructure.database.models.restaurant_order import (
    RestaurantOrder as RestaurantOrderModel,
)
from app.infrastructure.database.models.restaurant_order_item import (
    RestaurantOrderItem,
)
from app.infrastructure.unit_of_work import UnitOfWork
from app.schemas import (
    BranchAvailabilitySync,
    BranchSync,
    BusinessErrorCode,
    MenuItemAvailabilitySync,
    MenuItemSync,
    MenuSync,
    RestaurantOrder,
    RestaurantOrderResponse,
    RestaurantSync,
    SyncPayload,
    SyncResponse,
    ValidationIssue,
)


class DemoRestaurantService:
    def __init__(self, session_factory, kitchen_client):
        self.session_factory = session_factory
        self.kitchen_client = kitchen_client

    async def sync(self) -> SyncResponse:
        payload = await self.build_sync_payload()
        response = await self.kitchen_client.sync_catalog(
            payload.model_dump(mode="json")
        )
        return SyncResponse.model_validate(response)

    async def create_order(
        self,
        request: RestaurantOrder,
    ) -> RestaurantOrderResponse:
        request_hash = self._request_hash(request)
        async with UnitOfWork(self.session_factory) as uow:
            await uow.restaurant_orders.lock_external_id(request.order_id)
            existing = await uow.restaurant_orders.get_by_external_id(
                request.order_id
            )
            if existing is not None:
                if existing.request_hash != request_hash:
                    return self._rejected(
                        BusinessErrorCode.ORDER_ID_CONFLICT,
                        "Order ID was already used for another request",
                    )
                return self._stored_response(existing)

            branch = await uow.restaurant_branches.get_by_external_id(
                request.branch_external_id
            )
            if (
                branch is None
                or not branch.is_active
                or not branch.is_accepting_orders
            ):
                issue = ValidationIssue(
                    code=BusinessErrorCode.BRANCH_UNAVAILABLE,
                    message="Branch is unavailable",
                )
                uow.restaurant_orders.add(
                    RestaurantOrderModel(
                        external_id=request.order_id,
                        branch_id=branch.id if branch is not None else None,
                        branch_external_id=request.branch_external_id,
                        status="rejected",
                        accepted=False,
                        rejection_code=issue.code.value,
                        rejection_reason=issue.message,
                        request_hash=request_hash,
                    )
                )
                return RestaurantOrderResponse(accepted=False, reason=issue)

            validated_items = []
            issue: ValidationIssue | None = None
            for requested_item in request.items:
                menu_item = await uow.menu_items.get_by_external_id(
                    requested_item.menu_item_external_id
                )
                if menu_item is None:
                    issue = ValidationIssue(
                        code=BusinessErrorCode.PRODUCT_NOT_FOUND,
                        message="Product not found",
                        menu_item_external_id=(
                            requested_item.menu_item_external_id
                        ),
                    )
                    break
                relation = (
                    await uow.branch_menu_items.get_by_branch_and_menu_item(
                        branch.id, menu_item.id
                    )
                )
                if (
                    not menu_item.is_active
                    or relation is None
                    or not relation.is_available
                    or relation.price is None
                ):
                    issue = ValidationIssue(
                        code=BusinessErrorCode.PRODUCT_UNAVAILABLE,
                        message="Product is unavailable",
                        menu_item_external_id=menu_item.external_id,
                    )
                    break
                if relation.price != requested_item.unit_price:
                    issue = ValidationIssue(
                        code=BusinessErrorCode.PRICE_CHANGED,
                        message="Product price has changed",
                        menu_item_external_id=menu_item.external_id,
                        old_price=requested_item.unit_price,
                        current_price=relation.price,
                    )
                    break
                validated_items.append((requested_item, menu_item, relation))

            if issue is not None:
                uow.restaurant_orders.add(
                    RestaurantOrderModel(
                        external_id=request.order_id,
                        branch_id=branch.id,
                        branch_external_id=request.branch_external_id,
                        status="rejected",
                        accepted=False,
                        rejection_code=issue.code.value,
                        rejection_reason=issue.message,
                        rejection_menu_item_external_id=(
                            issue.menu_item_external_id
                        ),
                        rejection_old_price=issue.old_price,
                        rejection_current_price=issue.current_price,
                        request_hash=request_hash,
                    )
                )
                return RestaurantOrderResponse(accepted=False, reason=issue)

            order = uow.restaurant_orders.add(
                RestaurantOrderModel(
                    external_id=request.order_id,
                    branch_id=branch.id,
                    branch_external_id=request.branch_external_id,
                    status="accepted",
                    accepted=True,
                    rejection_code=None,
                    rejection_reason=None,
                    request_hash=request_hash,
                )
            )
            await uow.flush()
            for requested_item, menu_item, relation in validated_items:
                uow.restaurant_order_items.add(
                    RestaurantOrderItem(
                        order_id=order.id,
                        menu_item_id=menu_item.id,
                        menu_item_external_id=menu_item.external_id,
                        menu_item_name=menu_item.name,
                        quantity=requested_item.quantity,
                        unit_price=relation.price,
                    )
                )
            return RestaurantOrderResponse(
                accepted=True,
                restaurant_order_id=order.id,
            )

    async def build_sync_payload(self) -> SyncPayload:
        async with UnitOfWork(
            self.session_factory,
            isolation_level="REPEATABLE READ",
        ) as uow:
            branches = await uow.restaurant_branches.get_all()
            menu_items = await uow.menu_items.get_all()
            branch_menu_items = await uow.branch_menu_items.get_all()
            return SyncPayload(
                snapshot_id=uuid4(),
                schema_version=2,
                generated_at=datetime.now(UTC),
                restaurant=RestaurantSync(
                    external_id=settings.restaurant_external_id,
                    name=settings.restaurant_name,
                    description=settings.restaurant_description,
                ),
                branches=self._build_branches(branches),
                menu=self._build_menu(menu_items),
                availability=self._build_availability(
                    branches, menu_items, branch_menu_items
                ),
            )

    @staticmethod
    def _stored_response(
        order: RestaurantOrderModel,
    ) -> RestaurantOrderResponse:
        if order.accepted:
            return RestaurantOrderResponse(
                accepted=True,
                restaurant_order_id=order.id,
            )
        return RestaurantOrderResponse(
            accepted=False,
            reason=ValidationIssue(
                code=BusinessErrorCode(order.rejection_code),
                message=order.rejection_reason,
                menu_item_external_id=(order.rejection_menu_item_external_id),
                old_price=order.rejection_old_price,
                current_price=order.rejection_current_price,
            ),
        )

    @staticmethod
    def _rejected(
        code: BusinessErrorCode,
        message: str,
    ) -> RestaurantOrderResponse:
        return RestaurantOrderResponse(
            accepted=False,
            reason=ValidationIssue(code=code, message=message),
        )

    @staticmethod
    def _request_hash(request: RestaurantOrder) -> str:
        canonical = json.dumps(
            request.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _build_branches(branches) -> list[BranchSync]:
        return [
            BranchSync(
                external_id=branch.external_id,
                name=branch.name,
                address=branch.address,
                is_active=branch.is_active,
                is_accepting_orders=branch.is_accepting_orders,
                branch_version=branch.branch_version,
            )
            for branch in branches
        ]

    @staticmethod
    def _build_menu(menu_items) -> MenuSync:
        return MenuSync(
            external_id=settings.menu_external_id,
            name=settings.menu_name,
            items=[
                MenuItemSync(
                    external_id=item.external_id,
                    name=item.name,
                    description=item.description,
                    is_active=item.is_active,
                )
                for item in menu_items
            ],
        )

    @staticmethod
    def _build_availability(
        branches, menu_items, branch_menu_items
    ) -> list[BranchAvailabilitySync]:
        availability_map = {
            (item.branch_id, item.menu_item_id): item
            for item in branch_menu_items
        }
        return [
            BranchAvailabilitySync(
                branch_external_id=branch.external_id,
                items=[
                    MenuItemAvailabilitySync(
                        menu_item_external_id=menu_item.external_id,
                        price=(
                            relation.price if relation is not None else None
                        ),
                        is_available=(
                            relation is not None
                            and relation.is_available
                            and relation.price is not None
                            and branch.is_active
                            and menu_item.is_active
                        ),
                    )
                    for menu_item in menu_items
                    for relation in [
                        availability_map.get((branch.id, menu_item.id))
                    ]
                ],
            )
            for branch in branches
        ]
