from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin
from app.modules.orders.errors import InvalidOrderTransitionError
from app.modules.orders.models.order_item import OrderItem, OrderItemSnapshot


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    restaurant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "restaurants.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    branch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "restaurant_branches.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    external_order_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    restaurant_order_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    request_hash: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    rejection_code: Mapped[str | None] = mapped_column(String, nullable=True)
    rejection_message: Mapped[str | None] = mapped_column(
        String, nullable=True
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

    __table_args__ = (
        UniqueConstraint(
            "restaurant_id",
            "external_order_id",
            name="uq_order_restaurant_external_id",
        ),
        UniqueConstraint(
            "restaurant_id",
            "restaurant_order_id",
            name="uq_order_restaurant_order_id",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')",
            name="ck_order_status",
        ),
        CheckConstraint(
            "(status = 'confirmed' AND restaurant_order_id IS NOT NULL "
            "AND rejection_code IS NULL AND rejection_message IS NULL) OR "
            "(status = 'rejected' AND restaurant_order_id IS NULL "
            "AND rejection_code IS NOT NULL AND rejection_message IS NOT NULL) OR "
            "(status = 'pending' AND restaurant_order_id IS NULL "
            "AND rejection_code IS NULL AND rejection_message IS NULL)",
            name="ck_order_result_consistency",
        ),
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )

    @classmethod
    def create_pending(
        cls,
        user_id: UUID,
        restaurant_id: UUID,
        branch_id: UUID,
        external_order_id: str,
        request_hash: str,
        items: list[OrderItemSnapshot],
    ) -> "Order":
        if not items:
            raise ValueError("Order must contain at least one item")
        seen_menu_item_ids: set[UUID] = set()
        for item in items:
            if item.quantity <= 0:
                raise ValueError("Order item quantity must be positive")
            if item.unit_price <= 0:
                raise ValueError("Order item unit price must be positive")
            if item.menu_item_id in seen_menu_item_ids:
                raise ValueError("Order cannot contain duplicate menu items")
            seen_menu_item_ids.add(item.menu_item_id)

        order_id = uuid4()
        return cls(
            id=order_id,
            user_id=user_id,
            restaurant_id=restaurant_id,
            branch_id=branch_id,
            external_order_id=external_order_id,
            restaurant_order_id=None,
            request_hash=request_hash,
            status="pending",
            items=[
                OrderItem(
                    order_id=order_id,
                    menu_item_id=item.menu_item_id,
                    product_name=item.product_name,
                    unit_price=item.unit_price,
                    quantity=item.quantity,
                )
                for item in items
            ],
        )

    def confirm(self, restaurant_order_id: str) -> None:
        if self.status != "pending":
            raise InvalidOrderTransitionError(
                "Only pending orders can be confirmed"
            )
        if not restaurant_order_id or not restaurant_order_id.strip():
            raise ValueError("Restaurant order ID must be nonempty")
        self.status = "confirmed"
        self.restaurant_order_id = restaurant_order_id
        self.rejection_code = None
        self.rejection_message = None
        self.rejection_menu_item_external_id = None
        self.rejection_old_price = None
        self.rejection_current_price = None

    def reject(
        self,
        code: str,
        message: str,
        menu_item_external_id: str | None = None,
        old_price: int | None = None,
        current_price: int | None = None,
    ) -> None:
        if self.status != "pending":
            raise InvalidOrderTransitionError(
                "Only pending orders can be rejected"
            )
        if not code or not code.strip():
            raise ValueError("Rejection code must be nonempty")
        if not message or not message.strip():
            raise ValueError("Rejection message must be nonempty")
        if old_price is not None and old_price <= 0:
            raise ValueError("Old price must be positive")
        if current_price is not None and current_price <= 0:
            raise ValueError("Current price must be positive")
        self.status = "rejected"
        self.restaurant_order_id = None
        self.rejection_code = code
        self.rejection_message = message
        self.rejection_menu_item_external_id = menu_item_external_id
        self.rejection_old_price = old_price
        self.rejection_current_price = current_price
