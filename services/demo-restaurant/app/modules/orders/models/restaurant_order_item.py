from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.catalog.models.menu_item import MenuItem
    from app.modules.orders.models.restaurant_order import (
        RestaurantOrder,
    )


class RestaurantOrderItem(TimestampMixin, Base):
    __tablename__ = "restaurant_order_items"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "restaurant_orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    menu_item_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "menu_items.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    menu_item_external_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    menu_item_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_price: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    order: Mapped["RestaurantOrder"] = relationship(
        "RestaurantOrder",
        back_populates="items",
    )

    menu_item: Mapped["MenuItem | None"] = relationship(
        "MenuItem",
    )

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_restaurant_order_item_quantity_positive",
        ),
        CheckConstraint(
            "unit_price > 0",
            name="ck_restaurant_order_item_price_positive",
        ),
    )
