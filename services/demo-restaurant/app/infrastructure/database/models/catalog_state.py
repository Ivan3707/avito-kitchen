from sqlalchemy import BigInteger, CheckConstraint, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class CatalogState(Base):
    __tablename__ = "catalog_state"

    id: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        autoincrement=False,
    )

    catalog_revision: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
    )

    restaurant_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    restaurant_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    menu_name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "id = 1",
            name="ck_catalog_state_singleton",
        ),
        CheckConstraint(
            "catalog_revision >= 0",
            name="ck_catalog_state_revision_non_negative",
        ),
    )
