from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin
from app.modules.cart.errors import CartItemNotFoundError
from app.modules.cart.models.cart_item import CartItem

if TYPE_CHECKING:
    from app.modules.catalog.models.menu_item import MenuItem


class Cart(TimestampMixin, Base):
    __tablename__ = "carts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
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

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "branch_id",
            name="uq_cart_user_branch",
        ),
    )

    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
    )

    def _find_item(self, menu_item_id: UUID) -> CartItem | None:
        return next(
            (item for item in self.items if item.menu_item_id == menu_item_id),
            None,
        )

    def add_item(self, menu_item: "MenuItem", quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Cart item quantity must be positive")
        item = self._find_item(menu_item.id)
        if item is not None:
            item.quantity += quantity
        else:
            self.items.append(
                CartItem(
                    menu_item_id=menu_item.id,
                    menu_item=menu_item,
                    quantity=quantity,
                )
            )

    def update_item_quantity(self, menu_item_id: UUID, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("Cart item quantity must be positive")
        item = self._find_item(menu_item_id)
        if item is None:
            raise CartItemNotFoundError
        item.quantity = quantity

    def remove_item(self, menu_item_id: UUID) -> None:
        item = self._find_item(menu_item_id)
        if item is None:
            raise CartItemNotFoundError
        self.items.remove(item)

    def remove_ordered_quantities(
        self, ordered_quantities: dict[UUID, int]
    ) -> None:
        if any(quantity < 0 for quantity in ordered_quantities.values()):
            raise ValueError("Ordered quantity cannot be negative")
        for item in list(self.items):
            ordered = ordered_quantities.get(item.menu_item_id, 0)
            if ordered == 0:
                continue
            if item.quantity <= ordered:
                self.items.remove(item)
            else:
                item.quantity -= ordered
