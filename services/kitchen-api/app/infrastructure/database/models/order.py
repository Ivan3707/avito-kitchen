from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, TimestampMixin


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "customers.id",
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

    restaurant_order_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    request_hash: Mapped[str] = mapped_column(
        String,
        nullable=False,
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
    )
