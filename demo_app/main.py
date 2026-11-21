# ruff: noqa: E501

from __future__ import annotations

import html
import random
import secrets
from dataclasses import dataclass
from urllib.parse import parse_qs

from fastapi import Cookie, FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="PixelPilot Demo Shop")


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price: float
    description: str


PRODUCTS = (
    Product("aurora-mug", "Aurora Mug", 18.0, "A ceramic mug with a midnight glaze."),
    Product("pixel-tote", "Pixel Tote", 24.0, "A sturdy canvas tote for daily missions."),
    Product("orbit-notebook", "Orbit Notebook", 12.0, "A dotted notebook with 160 pages."),
)
CARTS: dict[str, dict[str, int]] = {}


def _mutation(enabled: bool) -> tuple[str, str, str]:
    if not enabled:
        return "card", "primary", "#3157d5"
    token = secrets.token_hex(4)
    return f"item-{token}", f"action-{token}", random.choice(("#b42318", "#067647", "#6941c6"))


def _page(title: str, content: str, *, mutate: bool, color: str) -> str:
    flex = "row-reverse" if mutate and random.choice((True, False)) else "row"
    cart_id = secrets.token_hex(4) if mutate else "cart-nav"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{html.escape(title)}</title><style>
body{{font:16px system-ui;margin:0;background:#f5f7fb;color:#17202a}}
header,main{{max-width:900px;margin:auto;padding:20px}} header{{display:flex;justify-content:space-between}}
.grid{{display:flex;flex-direction:{flex};flex-wrap:wrap;gap:16px}} article{{background:white;padding:18px;border-radius:12px;min-width:220px;flex:1}}
button,.button{{background:{color};color:white;border:0;border-radius:8px;padding:10px 16px;cursor:pointer;text-decoration:none}}
input{{padding:9px;border:1px solid #aaa;border-radius:7px}} .notice{{padding:12px;background:#fff4e5;border-radius:8px}}
</style></head><body><header><strong>PixelPilot Shop</strong><nav><a href="/?mutate={int(mutate)}">Products</a> · <a id="{cart_id}" href="/cart?mutate={int(mutate)}">Cart</a></nav></header>
<main><h1>{html.escape(title)}</h1>{content}</main></body></html>"""


def _cart_id(cart_id: str | None) -> str:
    return cart_id or secrets.token_urlsafe(12)


def _cart_rows(cart: dict[str, int]) -> tuple[str, float]:
    rows: list[str] = []
    total = 0.0
    for product in PRODUCTS:
        quantity = cart.get(product.sku, 0)
        if quantity:
            subtotal = product.price * quantity
            total += subtotal
            rows.append(f"<li>{html.escape(product.name)} × {quantity} — ${subtotal:.2f}</li>")
    return "".join(rows), total


@app.get("/", response_class=HTMLResponse)
async def products(mutate: bool = False) -> HTMLResponse:
    card_class, button_class, color = _mutation(mutate)
    items = list(PRODUCTS)
    if mutate:
        random.shuffle(items)
    cards = []
    for product in items:
        element_id = secrets.token_hex(5) if mutate else f"product-{product.sku}"
        cards.append(
            f'<article class="{card_class}" id="{element_id}"><h2>{html.escape(product.name)}</h2>'
            f"<p>{html.escape(product.description)}</p><p>${product.price:.2f}</p>"
            f'<form action="/cart/add" method="post"><input type="hidden" name="sku" value="{product.sku}">'
            f'<input type="hidden" name="mutate" value="{int(mutate)}">'
            f'<button class="{button_class}" type="submit">Add {html.escape(product.name)} to cart</button></form></article>'
        )
    return HTMLResponse(
        _page(
            "Products",
            f'<section class="grid">{"".join(cards)}</section>',
            mutate=mutate,
            color=color,
        )
    )


async def _form(request: Request) -> dict[str, str]:
    values = parse_qs((await request.body()).decode(), keep_blank_values=True)
    return {key: items[-1] for key, items in values.items()}


@app.post("/cart/add", response_class=HTMLResponse)
async def add_to_cart(request: Request, cart_id: str | None = Cookie(None)) -> HTMLResponse:
    form = await _form(request)
    sku = form.get("sku", "")
    mutate = form.get("mutate") == "1"
    identity = _cart_id(cart_id)
    cart = CARTS.setdefault(identity, {})
    if sku in {product.sku for product in PRODUCTS}:
        cart[sku] = cart.get(sku, 0) + 1
    response = await show_cart(mutate=mutate, cart_id=identity)
    response.set_cookie("cart_id", identity, httponly=True, samesite="lax")
    return response


@app.get("/cart", response_class=HTMLResponse)
async def show_cart(mutate: bool = False, cart_id: str | None = Cookie(None)) -> HTMLResponse:
    rows, total = _cart_rows(CARTS.get(_cart_id(cart_id), {}))
    _, _, color = _mutation(mutate)
    if not rows:
        body = f'<p class="notice">Your cart is empty.</p><a class="button" href="/?mutate={int(mutate)}">Browse products</a>'
    else:
        body = f'<ul>{rows}</ul><p><strong>Cart total: ${total:.2f}</strong></p><a class="button" href="/checkout?mutate={int(mutate)}">Proceed to checkout</a>'
    return HTMLResponse(_page("Your cart", body, mutate=mutate, color=color))


@app.get("/checkout", response_class=HTMLResponse)
async def checkout(mutate: bool = False, cart_id: str | None = Cookie(None)) -> HTMLResponse:
    rows, total = _cart_rows(CARTS.get(_cart_id(cart_id), {}))
    _, _, color = _mutation(mutate)
    if not rows:
        return HTMLResponse(
            _page(
                "Checkout",
                '<p class="notice">Your cart is empty. Add a product before checkout.</p>',
                mutate=mutate,
                color=color,
            )
        )
    body = f"""<ul>{rows}</ul><p>Subtotal: ${total:.2f}</p>
<form action="/checkout" method="post"><label for="coupon">Coupon code</label>
<input id="coupon" name="coupon" autocomplete="off"><input type="hidden" name="mutate" value="{int(mutate)}">
<button type="submit">Place order</button></form>"""
    return HTMLResponse(_page("Checkout", body, mutate=mutate, color=color))


@app.post("/checkout", response_class=HTMLResponse)
async def place_order(request: Request, cart_id: str | None = Cookie(None)) -> HTMLResponse:
    form = await _form(request)
    coupon = form.get("coupon", "")
    mutate = form.get("mutate") == "1"
    identity = _cart_id(cart_id)
    cart = CARTS.get(identity, {})
    rows, subtotal = _cart_rows(cart)
    _, _, color = _mutation(mutate)
    if not rows:
        return HTMLResponse(
            _page(
                "Checkout",
                '<p class="notice">Your cart is empty. Add a product before checkout.</p>',
                mutate=mutate,
                color=color,
            ),
            status_code=400,
        )
    normalized = coupon.strip().upper()
    if normalized == "OLD50":
        body = f'<p class="notice">Coupon OLD50 has expired.</p><a class="button" href="/checkout?mutate={int(mutate)}">Return to checkout</a>'
        return HTMLResponse(
            _page("Coupon expired", body, mutate=mutate, color=color), status_code=400
        )
    discount = subtotal * 0.1 if normalized == "SAVE10" else 0.0
    total = subtotal - discount
    CARTS[identity] = {}
    body = f"<p>Order confirmed.</p><p>Discount: ${discount:.2f}</p><p><strong>Total paid: ${total:.2f}</strong></p>"
    return HTMLResponse(_page("Confirmation", body, mutate=mutate, color=color))


@app.get("/scroll", response_class=HTMLResponse)
@app.post("/scroll", response_class=HTMLResponse)
async def scroll_page(request: Request, mutate: bool = False) -> HTMLResponse:
    _, button_class, color = _mutation(mutate)
    spacer_height = random.choice((1300, 1500, 1700)) if mutate else 1400
    if request.method == "POST":
        body = (
            '<div class="notice"><p>Scroll target reached and confirmed.</p></div>'
            f'<a class="button" href="/scroll?mutate={int(mutate)}">Reset</a>'
        )
    else:
        btn_id = secrets.token_hex(4) if mutate else "scroll-target-btn"
        body = (
            "<p>Scroll down to reach the bottom confirmation action.</p>"
            f'<div style="height:{spacer_height}px;background:repeating-linear-gradient(45deg,#fafafa,#fafafa 20px,#f0f0f0 20px,#f0f0f0 40px);margin:20px 0;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#888;">'
            "<span>[Long scrollable content area]</span></div>"
            '<form action="/scroll" method="post">'
            f'<input type="hidden" name="mutate" value="{int(mutate)}">'
            f'<button id="{btn_id}" class="{button_class}" type="submit">Confirm bottom action</button>'
            "</form>"
        )
    return HTMLResponse(_page("Scroll target", body, mutate=mutate, color=color))


@app.get("/modal", response_class=HTMLResponse)
@app.post("/modal", response_class=HTMLResponse)
async def modal_page(
    request: Request, mutate: bool = False, accepted_cookies: str | None = Cookie(None)
) -> HTMLResponse:
    card_class, button_class, color = _mutation(mutate)
    action = ""
    if request.method == "POST":
        form = await _form(request)
        action = form.get("action", "")
        if "mutate" in form:
            mutate = form["mutate"] == "1"

    cookies_dismissed = accepted_cookies == "1" or action == "accept_cookies"

    if action == "claim_deal" and cookies_dismissed:
        body = (
            '<p class="notice">Special deal claimed successfully.</p>'
            f'<a class="button" href="/modal?mutate={int(mutate)}">Reset</a>'
        )
        return HTMLResponse(_page("Special Deal", body, mutate=mutate, color=color))

    modal_html = ""
    if not cookies_dismissed:
        modal_id = secrets.token_hex(4) if mutate else "cookie-modal"
        modal_html = (
            f'<div id="{modal_id}" style="position:fixed;inset:0;background:rgba(0,0,0,0.65);z-index:9999;display:flex;align-items:center;justify-content:center;">'
            '<div style="background:white;padding:30px;border-radius:12px;max-width:400px;text-align:center;box-shadow:0 10px 25px rgba(0,0,0,0.3);">'
            "<h2>Cookie Consent</h2>"
            "<p>We use cookies to personalize deals. Please accept before continuing.</p>"
            '<form action="/modal" method="post">'
            '<input type="hidden" name="action" value="accept_cookies">'
            f'<input type="hidden" name="mutate" value="{int(mutate)}">'
            f'<button class="{button_class}" type="submit">Accept cookies</button>'
            "</form>"
            "</div></div>"
        )

    main_html = (
        f"{modal_html}"
        f'<div class="{card_class}">'
        "<h2>Exclusive Member Deal</h2>"
        "<p>Unlock your exclusive promo code below.</p>"
        '<form action="/modal" method="post">'
        '<input type="hidden" name="action" value="claim_deal">'
        f'<input type="hidden" name="mutate" value="{int(mutate)}">'
        f'<button class="{button_class}" type="submit">Claim special deal</button>'
        "</form>"
        "</div>"
    )
    response = HTMLResponse(_page("Modal Deal", main_html, mutate=mutate, color=color))
    if action == "accept_cookies":
        response.set_cookie("accepted_cookies", "1", httponly=True, samesite="lax")
    return response


@app.get("/ambiguous", response_class=HTMLResponse)
@app.post("/ambiguous", response_class=HTMLResponse)
async def ambiguous_page(request: Request, mutate: bool = False) -> HTMLResponse:
    card_class, button_class, color = _mutation(mutate)
    if request.method == "POST":
        form = await _form(request)
        item = form.get("item", "")
        if item == "Target Widget":
            body = (
                '<p class="notice">Target Widget added to cart.</p>'
                f'<a class="button" href="/ambiguous?mutate={int(mutate)}">Reset</a>'
            )
        else:
            body = (
                f'<p class="notice">Wrong item added: {html.escape(item)}.</p>'
                f'<a class="button" href="/ambiguous?mutate={int(mutate)}">Try again</a>'
            )
        return HTMLResponse(_page("Ambiguous result", body, mutate=mutate, color=color))

    items = ["Alpha Trinket", "Target Widget", "Beta Bauble"]
    if mutate:
        random.shuffle(items)
    cards = []
    for item in items:
        cid = secrets.token_hex(4) if mutate else f"card-{item.lower().replace(' ', '-')}"
        cards.append(
            f'<article class="{card_class}" id="{cid}">'
            f"<h2>{html.escape(item)}</h2>"
            "<p>Essential hardware utility.</p>"
            '<form action="/ambiguous" method="post">'
            f'<input type="hidden" name="item" value="{html.escape(item)}">'
            f'<input type="hidden" name="mutate" value="{int(mutate)}">'
            f'<button class="{button_class}" type="submit">Add</button>'
            "</form></article>"
        )
    return HTMLResponse(
        _page(
            "Ambiguous items",
            f'<section class="grid">{"".join(cards)}</section>',
            mutate=mutate,
            color=color,
        )
    )


@app.get("/icons", response_class=HTMLResponse)
@app.post("/icons", response_class=HTMLResponse)
async def icons_page(request: Request, mutate: bool = False) -> HTMLResponse:
    card_class, button_class, color = _mutation(mutate)
    if request.method == "POST":
        form = await _form(request)
        icon = form.get("icon", "")
        if icon == "cart":
            body = (
                '<p class="notice">Cart icon selected.</p>'
                f'<a class="button" href="/icons?mutate={int(mutate)}">Reset</a>'
            )
        else:
            body = (
                f'<p class="notice">Selected {html.escape(icon)} icon.</p>'
                f'<a class="button" href="/icons?mutate={int(mutate)}">Try again</a>'
            )
        return HTMLResponse(_page("Icons result", body, mutate=mutate, color=color))

    icons = [("search", "🔍"), ("star", "⭐"), ("cart", "🛒")]
    if mutate:
        random.shuffle(icons)
    buttons = []
    for icon_name, icon_char in icons:
        bid = secrets.token_hex(4) if mutate else f"icon-{icon_name}"
        buttons.append(
            '<form action="/icons" method="post" style="display:inline-block;margin:8px;">'
            f'<input type="hidden" name="icon" value="{icon_name}">'
            f'<input type="hidden" name="mutate" value="{int(mutate)}">'
            f'<button id="{bid}" class="{button_class}" type="submit" style="font-size:24px;padding:8px 14px;">{icon_char}</button>'
            "</form>"
        )
    content = f'<div class="{card_class}"><h2>Action Bar</h2><div>{"".join(buttons)}</div></div>'
    return HTMLResponse(_page("Icon navigation", content, mutate=mutate, color=color))
