from __future__ import annotations

from pathlib import Path

from playwright.async_api import Browser


async def run_baseline(browser: Browser, story: Path, base_url: str, mutate: bool) -> bool:
    page = await browser.new_page()
    query = f"?mutate={int(mutate)}"
    try:
        await page.goto(f"{base_url}/{query}", wait_until="domcontentloaded")
        if story.name == "empty_cart_checkout.md":
            await page.locator("#cart-nav").click(timeout=3_000)
            return "Your cart is empty" in await page.locator("body").inner_text()
        product_id = (
            "product-aurora-mug"
            if story.name == "checkout_valid_coupon.md"
            else "product-pixel-tote"
        )
        await page.locator(f"#{product_id} button").click(timeout=3_000)
        await page.locator("a.button").click(timeout=3_000)
        coupon = "SAVE10" if story.name == "checkout_valid_coupon.md" else "OLD50"
        await page.locator("#coupon").fill(coupon, timeout=3_000)
        await page.locator("form button").click(timeout=3_000)
        body = await page.locator("body").inner_text()
        expected = "Order confirmed" if coupon == "SAVE10" else "Coupon OLD50 has expired"
        return expected in body
    except Exception:
        return False
    finally:
        await page.close()
