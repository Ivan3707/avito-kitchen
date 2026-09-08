import pytest
from pydantic import ValidationError

from app.integration.schemas.common import BusinessErrorCode
from app.integration.schemas.orders import (
    CreateOrderRequest,
    CreateOrderResponse,
    OrderItemRequest,
    OrderValidationRequest,
    OrderValidationResponse,
    ValidationIssue,
)

# ============================================================
# Positive scenarios
# ============================================================


def test_valid_order_item():
    item = OrderItemRequest(
        menu_item_external_id="pizza-pepperoni",
        quantity=2,
        unit_price=59900,
    )

    assert item.menu_item_external_id == "pizza-pepperoni"
    assert item.quantity == 2
    assert item.unit_price == 59900


def test_valid_order_validation_request():
    request = OrderValidationRequest(
        branch_external_id="branch-center",
        items=[
            OrderItemRequest(
                menu_item_external_id="pizza-pepperoni",
                quantity=2,
                unit_price=59900,
            ),
            OrderItemRequest(
                menu_item_external_id="cola",
                quantity=1,
                unit_price=15000,
            ),
        ],
    )

    assert request.branch_external_id == "branch-center"
    assert len(request.items) == 2


def test_valid_branch_unavailable_issue():
    issue = ValidationIssue(
        code=BusinessErrorCode.BRANCH_UNAVAILABLE,
        message="Branch is not accepting orders",
    )

    assert issue.code == BusinessErrorCode.BRANCH_UNAVAILABLE
    assert issue.menu_item_external_id is None
    assert issue.old_price is None
    assert issue.current_price is None


def test_valid_product_not_found_issue():
    issue = ValidationIssue(
        code=BusinessErrorCode.PRODUCT_NOT_FOUND,
        message="Product was not found",
        menu_item_external_id="pizza-pepperoni",
    )

    assert issue.code == BusinessErrorCode.PRODUCT_NOT_FOUND
    assert issue.menu_item_external_id == "pizza-pepperoni"


def test_valid_product_unavailable_issue():
    issue = ValidationIssue(
        code=BusinessErrorCode.PRODUCT_UNAVAILABLE,
        message="Product is unavailable",
        menu_item_external_id="pizza-pepperoni",
    )

    assert issue.code == BusinessErrorCode.PRODUCT_UNAVAILABLE
    assert issue.menu_item_external_id == "pizza-pepperoni"


def test_valid_insufficient_quantity_issue():
    issue = ValidationIssue(
        code=BusinessErrorCode.INSUFFICIENT_QUANTITY,
        message="Requested quantity is unavailable",
        menu_item_external_id="pizza-pepperoni",
    )

    assert issue.code == BusinessErrorCode.INSUFFICIENT_QUANTITY
    assert issue.menu_item_external_id == "pizza-pepperoni"


def test_valid_price_changed_issue():
    issue = ValidationIssue(
        code=BusinessErrorCode.PRICE_CHANGED,
        message="Product price has changed",
        menu_item_external_id="pizza-pepperoni",
        old_price=59900,
        current_price=64900,
    )

    assert issue.code == BusinessErrorCode.PRICE_CHANGED
    assert issue.menu_item_external_id == "pizza-pepperoni"
    assert issue.old_price == 59900
    assert issue.current_price == 64900


def test_valid_order_validation_response():
    response = OrderValidationResponse(
        valid=False,
        issues=[
            ValidationIssue(
                code=BusinessErrorCode.PRODUCT_UNAVAILABLE,
                message="Product is unavailable",
                menu_item_external_id="pizza-pepperoni",
            ),
        ],
    )

    assert response.valid is False
    assert len(response.issues) == 1


def test_valid_order_validation_response_without_issues():
    response = OrderValidationResponse(
        valid=True,
        issues=[],
    )

    assert response.valid is True
    assert response.issues == []


def test_valid_create_order_request():
    request = CreateOrderRequest(
        order_id="order-123",
        branch_external_id="branch-center",
        items=[
            OrderItemRequest(
                menu_item_external_id="pizza-pepperoni",
                quantity=2,
                unit_price=59900,
            ),
        ],
    )

    assert request.order_id == "order-123"
    assert request.branch_external_id == "branch-center"
    assert len(request.items) == 1


def test_valid_accepted_create_order_response():
    response = CreateOrderResponse(
        accepted=True,
        restaurant_order_id="restaurant-order-456",
    )

    assert response.accepted is True
    assert response.restaurant_order_id == "restaurant-order-456"
    assert response.reason is None


def test_valid_rejected_create_order_response():
    response = CreateOrderResponse(
        accepted=False,
        reason=ValidationIssue(
            code=BusinessErrorCode.PRODUCT_UNAVAILABLE,
            message="Product is unavailable",
            menu_item_external_id="pizza-1",
        ),
    )

    assert response.accepted is False
    assert response.reason is not None
    assert response.reason.code == BusinessErrorCode.PRODUCT_UNAVAILABLE
    assert response.restaurant_order_id is None


# ============================================================
# OrderItemRequest validation
# ============================================================


def test_order_item_rejects_empty_external_id():
    with pytest.raises(ValidationError) as exc_info:
        OrderItemRequest(
            menu_item_external_id="",
            quantity=1,
            unit_price=10000,
        )

    assert exc_info.value.errors()[0]["loc"] == ("menu_item_external_id",)


def test_order_item_rejects_zero_quantity():
    with pytest.raises(ValidationError) as exc_info:
        OrderItemRequest(
            menu_item_external_id="pizza-pepperoni",
            quantity=0,
            unit_price=10000,
        )

    assert exc_info.value.errors()[0]["loc"] == ("quantity",)


def test_order_item_rejects_negative_quantity():
    with pytest.raises(ValidationError) as exc_info:
        OrderItemRequest(
            menu_item_external_id="pizza-pepperoni",
            quantity=-1,
            unit_price=10000,
        )

    assert exc_info.value.errors()[0]["loc"] == ("quantity",)


def test_order_item_rejects_zero_unit_price():
    with pytest.raises(ValidationError) as exc_info:
        OrderItemRequest(
            menu_item_external_id="pizza-pepperoni",
            quantity=1,
            unit_price=0,
        )

    assert exc_info.value.errors()[0]["loc"] == ("unit_price",)


def test_order_item_rejects_negative_unit_price():
    with pytest.raises(ValidationError) as exc_info:
        OrderItemRequest(
            menu_item_external_id="pizza-pepperoni",
            quantity=1,
            unit_price=-100,
        )

    assert exc_info.value.errors()[0]["loc"] == ("unit_price",)


# ============================================================
# OrderValidationRequest validation
# ============================================================


def test_order_validation_request_rejects_empty_branch_external_id():
    with pytest.raises(ValidationError) as exc_info:
        OrderValidationRequest(
            branch_external_id="",
            items=[],
        )

    assert exc_info.value.errors()[0]["loc"] == ("branch_external_id",)


# ============================================================
# ValidationIssue semantic validation
# ============================================================


@pytest.mark.parametrize(
    "code",
    [
        BusinessErrorCode.PRODUCT_NOT_FOUND,
        BusinessErrorCode.PRODUCT_UNAVAILABLE,
        BusinessErrorCode.INSUFFICIENT_QUANTITY,
    ],
)
def test_product_level_issue_requires_menu_item_external_id(code):
    with pytest.raises(ValidationError):
        ValidationIssue(
            code=code,
            message="Product issue",
        )


def test_branch_unavailable_issue_rejects_menu_item_external_id():
    with pytest.raises(ValidationError):
        ValidationIssue(
            code=BusinessErrorCode.BRANCH_UNAVAILABLE,
            message="Branch is unavailable",
            menu_item_external_id="pizza-pepperoni",
        )


def test_branch_unavailable_issue_rejects_prices():
    with pytest.raises(ValidationError):
        ValidationIssue(
            code=BusinessErrorCode.BRANCH_UNAVAILABLE,
            message="Branch is unavailable",
            old_price=50000,
            current_price=60000,
        )


def test_product_issue_rejects_prices():
    with pytest.raises(ValidationError):
        ValidationIssue(
            code=BusinessErrorCode.PRODUCT_UNAVAILABLE,
            message="Product is unavailable",
            menu_item_external_id="pizza-pepperoni",
            old_price=50000,
            current_price=60000,
        )


def test_price_changed_requires_menu_item_external_id():
    with pytest.raises(ValidationError):
        ValidationIssue(
            code=BusinessErrorCode.PRICE_CHANGED,
            message="Price changed",
            old_price=50000,
            current_price=60000,
        )


def test_price_changed_requires_old_price():
    with pytest.raises(ValidationError):
        ValidationIssue(
            code=BusinessErrorCode.PRICE_CHANGED,
            message="Price changed",
            menu_item_external_id="pizza-pepperoni",
            current_price=60000,
        )


def test_price_changed_requires_current_price():
    with pytest.raises(ValidationError):
        ValidationIssue(
            code=BusinessErrorCode.PRICE_CHANGED,
            message="Price changed",
            menu_item_external_id="pizza-pepperoni",
            old_price=50000,
        )


def test_price_changed_rejects_zero_old_price():
    with pytest.raises(ValidationError):
        ValidationIssue(
            code=BusinessErrorCode.PRICE_CHANGED,
            message="Price changed",
            menu_item_external_id="pizza-pepperoni",
            old_price=0,
            current_price=60000,
        )


def test_price_changed_rejects_negative_current_price():
    with pytest.raises(ValidationError):
        ValidationIssue(
            code=BusinessErrorCode.PRICE_CHANGED,
            message="Price changed",
            menu_item_external_id="pizza-pepperoni",
            old_price=50000,
            current_price=-1,
        )


# ============================================================
# OrderValidationResponse semantic validation
# ============================================================


def test_valid_response_requires_no_issues():
    with pytest.raises(ValidationError):
        OrderValidationResponse(
            valid=True,
            issues=[
                ValidationIssue(
                    code=BusinessErrorCode.PRODUCT_UNAVAILABLE,
                    message="Product is unavailable",
                    menu_item_external_id="pizza-pepperoni",
                ),
            ],
        )


def test_invalid_response_requires_issues():
    with pytest.raises(ValidationError):
        OrderValidationResponse(
            valid=False,
            issues=[],
        )


# ============================================================
# CreateOrderRequest validation
# ============================================================


def test_create_order_request_rejects_empty_order_id():
    with pytest.raises(ValidationError) as exc_info:
        CreateOrderRequest(
            order_id="",
            branch_external_id="branch-center",
            items=[],
        )

    assert exc_info.value.errors()[0]["loc"] == ("order_id",)


def test_create_order_request_rejects_empty_branch_external_id():
    with pytest.raises(ValidationError) as exc_info:
        CreateOrderRequest(
            order_id="order-123",
            branch_external_id="",
            items=[],
        )

    assert exc_info.value.errors()[0]["loc"] == ("branch_external_id",)


# ============================================================
# CreateOrderResponse semantic validation
# ============================================================


def test_accepted_response_requires_restaurant_order_id():
    with pytest.raises(ValidationError):
        CreateOrderResponse(
            accepted=True,
        )


def test_accepted_response_rejects_reason():
    with pytest.raises(ValidationError):
        CreateOrderResponse(
            accepted=True,
            restaurant_order_id="restaurant-order-456",
            reason="PRODUCT_UNAVAILABLE",
        )


def test_rejected_response_requires_reason():
    with pytest.raises(ValidationError):
        CreateOrderResponse(
            accepted=False,
        )


def test_rejected_response_rejects_restaurant_order_id():
    with pytest.raises(ValidationError):
        CreateOrderResponse(
            accepted=False,
            restaurant_order_id="restaurant-order-456",
            reason="PRODUCT_UNAVAILABLE",
        )


def test_accepted_response_rejects_empty_restaurant_order_id():
    with pytest.raises(ValidationError):
        CreateOrderResponse(
            accepted=True,
            restaurant_order_id="",
        )
