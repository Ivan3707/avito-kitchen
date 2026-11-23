from sqlalchemy import BigInteger, CheckConstraint, SmallInteger
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
