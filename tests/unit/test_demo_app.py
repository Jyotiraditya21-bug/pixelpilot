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


def test_scroll_fixture() -> None:
    client = TestClient(app)
    get_res = client.get("/scroll?mutate=1")
    assert get_res.status_code == 200
    assert "Confirm bottom action" in get_res.text
    post_res = client.post("/scroll", data={"mutate": "1"})
    assert post_res.status_code == 200
    assert "Scroll target reached and confirmed." in post_res.text


def test_modal_fixture() -> None:
    client = TestClient(app)
    get_res = client.get("/modal?mutate=1")
    assert get_res.status_code == 200
    assert "Accept cookies" in get_res.text

    # Accept cookies
    accept_res = client.post("/modal", data={"action": "accept_cookies", "mutate": "1"})
    assert accept_res.status_code == 200

    # Claim deal with cookie
    client.cookies.set("accepted_cookies", "1")
    claim_res = client.post("/modal", data={"action": "claim_deal", "mutate": "1"})
    assert claim_res.status_code == 200
    assert "Special deal claimed successfully." in claim_res.text


def test_ambiguous_fixture() -> None:
    client = TestClient(app)
    get_res = client.get("/ambiguous?mutate=1")
    assert get_res.status_code == 200
    assert "Target Widget" in get_res.text

    post_target = client.post("/ambiguous", data={"item": "Target Widget", "mutate": "1"})
    assert "Target Widget added to cart." in post_target.text

    post_wrong = client.post("/ambiguous", data={"item": "Alpha Trinket", "mutate": "1"})
    assert "Wrong item added" in post_wrong.text


def test_icons_fixture() -> None:
    client = TestClient(app)
    get_res = client.get("/icons?mutate=1")
    assert get_res.status_code == 200
    assert "🛒" in get_res.text

    post_cart = client.post("/icons", data={"icon": "cart", "mutate": "1"})
    assert "Cart icon selected." in post_cart.text
