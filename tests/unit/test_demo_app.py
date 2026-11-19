from demo_app.main import CARTS, app
from fastapi.testclient import TestClient


def test_valid_coupon_checkout() -> None:
    CARTS.clear()
    client = TestClient(app)
    added = client.post("/cart/add", data={"sku": "aurora-mug", "mutate": "0"})
    assert "Cart total: $18.00" in added.text
    result = client.post("/checkout", data={"coupon": "SAVE10", "mutate": "0"})
    assert result.status_code == 200
    assert "Order confirmed" in result.text
    assert "Total paid: $16.20" in result.text


def test_expired_coupon_does_not_clear_cart() -> None:
    CARTS.clear()
    client = TestClient(app)
    client.post("/cart/add", data={"sku": "pixel-tote", "mutate": "1"})
    result = client.post("/checkout", data={"coupon": "OLD50", "mutate": "1"})
    assert result.status_code == 400
    assert "has expired" in result.text
    assert "Pixel Tote" in client.get("/cart?mutate=1").text


def test_empty_cart_is_guarded() -> None:
    CARTS.clear()
    result = TestClient(app).get("/checkout")
    assert "Your cart is empty" in result.text
    assert "Place order" not in result.text
