from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin
from app.infrastructure.database.models.menu_item import MenuItem


class BranchMenuItem(TimestampMixin, Base):
    __tablename__ = "branch_menu_items"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    branch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "restaurant_branches.id",
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

    menu_item: Mapped["MenuItem"] = relationship(
        "MenuItem",
    )

    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "branch_id",
            "menu_item_id",
            name="uq_branch_menu_item",
        ),
    )