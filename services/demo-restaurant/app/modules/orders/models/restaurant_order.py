from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin
from app.modules.orders.models.restaurant_order_item import (
    RestaurantOrderItem,
    RestaurantOrderItemSnapshot,
)

if TYPE_CHECKING:
    from app.modules.catalog.models.restaurant_branch import (
        RestaurantBranch,
    )


class RestaurantOrder(TimestampMixin, Base):
    __tablename__ = "restaurant_orders"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    external_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    branch_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "restaurant_branches.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    branch_external_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    accepted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    rejection_code: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    rejection_menu_item_external_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    rejection_old_price: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    rejection_current_price: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    items: Mapped[list["RestaurantOrderItem"]] = relationship(
        "RestaurantOrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    branch: Mapped["RestaurantBranch | None"] = relationship(
        "RestaurantBranch",
    )

    __table_args__ = (
        UniqueConstraint(
            "external_id",
            name="uq_restaurant_order_external_id",
        ),
        CheckConstraint(
            """
            (
                accepted = TRUE
                AND status != 'rejected'
                AND rejection_reason IS NULL
                AND rejection_code IS NULL
            )
            OR
            (
                accepted = FALSE
                AND status = 'rejected'
                AND rejection_reason IS NOT NULL
                AND rejection_code IS NOT NULL
            )
            """,
            name="ck_restaurant_order_result_consistency",
        ),
        CheckConstraint(
            "status IN ('accepted', 'rejected', 'preparing', 'ready', 'completed', 'cancelled')",
            name="ck_restaurant_order_status",
        ),
    )

    @classmethod
    def create_accepted(
        cls,
        external_id: str,
        branch_id: UUID,
        branch_external_id: str,
        request_hash: str,
        items: list[RestaurantOrderItemSnapshot],
    ) -> "RestaurantOrder":
        if branch_id is None:
            raise ValueError("Accepted order requires a branch")
        if not items:
            raise ValueError("Accepted order requires items")
        internal_ids = set()
        external_ids = set()
        for item in items:
            if item.quantity <= 0 or item.unit_price <= 0:
                raise ValueError("Quantity and price must be positive")
            if (
                item.menu_item_id in internal_ids
                or item.menu_item_external_id in external_ids
            ):
                raise ValueError("Order items must be unique")
            internal_ids.add(item.menu_item_id)
            external_ids.add(item.menu_item_external_id)

        order_id = uuid4()
        return cls(
            id=order_id,
            external_id=external_id,
            branch_id=branch_id,
            branch_external_id=branch_external_id,
            request_hash=request_hash,
            status="accepted",
            accepted=True,
            rejection_code=None,
            rejection_reason=None,
            rejection_menu_item_external_id=None,
            rejection_old_price=None,
            rejection_current_price=None,
            items=[
                RestaurantOrderItem(
                    order_id=order_id,
                    menu_item_id=item.menu_item_id,
                    menu_item_external_id=item.menu_item_external_id,
                    menu_item_name=item.menu_item_name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                )
                for item in items
            ],
        )

    @classmethod
    def create_rejected(
        cls,
        external_id: str,
        branch_id: UUID | None,
        branch_external_id: str,
        request_hash: str,
        code: str,
        message: str,
        menu_item_external_id: str | None = None,
        old_price: int | None = None,
        current_price: int | None = None,
    ) -> "RestaurantOrder":
        if not code or not code.strip() or not message or not message.strip():
            raise ValueError("Rejection requires a code and message")
        if old_price is not None and old_price <= 0:
            raise ValueError("Old price must be positive")
        if current_price is not None and current_price <= 0:
            raise ValueError("Current price must be positive")
        return cls(
            external_id=external_id,
            branch_id=branch_id,
            branch_external_id=branch_external_id,
            request_hash=request_hash,
            status="rejected",
            accepted=False,
            rejection_code=code,
            rejection_reason=message,
            rejection_menu_item_external_id=menu_item_external_id,
            rejection_old_price=old_price,
            rejection_current_price=current_price,
            items=[],
        )
