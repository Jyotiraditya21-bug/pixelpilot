# ruff: noqa: E501

from __future__ import annotations

from typing import Any, cast

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from pixelpilot.models import ElementSnapshot, PageSnapshot

_SNAPSHOT_SCRIPT = r"""
() => {
  const roles = {A:'link',BUTTON:'button',INPUT:'textbox',SELECT:'combobox',TEXTAREA:'textbox',IMG:'img'};
  const nodes = [...document.querySelectorAll('a,button,input,select,textarea,[role],h1,h2,h3,p,li')];
  const elements = nodes.filter(n => {
    const r = n.getBoundingClientRect();
    const s = getComputedStyle(n);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  }).slice(0, 250).map(n => {
    const r = n.getBoundingClientRect();
    const label = n.getAttribute('aria-label') || n.labels?.[0]?.innerText || n.alt || n.title || '';
    const secret = n.tagName === 'INPUT' && n.type === 'password';
    const text = (secret ? '[REDACTED]' : (n.innerText || n.value || '')).trim().replace(/\s+/g, ' ').slice(0, 240);
    return {tag:n.tagName.toLowerCase(), role:n.getAttribute('role') || roles[n.tagName] || null,
      name:(label || text).slice(0, 160), text,
      bbox:{x:r.x,y:r.y,width:r.width,height:r.height}};
  });
  return {url:location.href,title:document.title,text:(document.body.innerText || '').slice(0,12000),
    elements,viewport_width:innerWidth,viewport_height:innerHeight};
}
"""


async def snapshot_page(page: Page) -> PageSnapshot:
    try:
        raw = cast(dict[str, Any], await page.evaluate(_SNAPSHOT_SCRIPT))
    except PlaywrightError:
        await page.wait_for_load_state("domcontentloaded")
        raw = cast(dict[str, Any], await page.evaluate(_SNAPSHOT_SCRIPT))
    elements = tuple(ElementSnapshot.model_validate(item) for item in raw["elements"])
    return PageSnapshot(
        url=str(raw["url"]),
        title=str(raw["title"]),
        text=str(raw["text"]),
        elements=elements,
        viewport_width=int(raw["viewport_width"]),
        viewport_height=int(raw["viewport_height"]),
    )
