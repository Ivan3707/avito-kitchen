from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, TimestampMixin


class Menu(TimestampMixin, Base):
    __tablename__ = "menus"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    restaurant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "restaurants.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    external_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "restaurant_id",
            name="uq_menu_restaurant_id",
        ),
    )
