from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.modules.orders.models.order import Order


@dataclass(frozen=True)
class OrderItemSnapshot:
    menu_item_id: UUID
    product_name: str
    unit_price: int
    quantity: int


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "orders.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    menu_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "menu_items.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    product_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    unit_price: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "unit_price > 0",
            name="ck_order_item_unit_price_positive",
        ),
        CheckConstraint(
            "quantity >= 1",
            name="ck_order_item_quantity_positive",
        ),
    )

    order: Mapped["Order"] = relationship(back_populates="items")
