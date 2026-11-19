from __future__ import annotations

import hashlib
import io

from PIL import Image
from pydantic import BaseModel, ConfigDict

from pixelpilot.models import ElementSnapshot


class Fingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tag: str
    role: str | None
    text: str
    region_hash: str
    phash: str


def average_hash(image: Image.Image) -> str:
    pixels = list(image.convert("L").resize((8, 8), Image.Resampling.LANCZOS).tobytes())
    average = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= average else "0" for pixel in pixels)
    return f"{int(bits, 2):016x}"


def hamming_distance(first: str, second: str) -> int:
    return (int(first, 16) ^ int(second, 16)).bit_count()


def fingerprint_element(
    image_bytes: bytes,
    element: ElementSnapshot,
    viewport_width: int,
    viewport_height: int,
) -> Fingerprint:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    x_scale = image.width / viewport_width
    y_scale = image.height / viewport_height
    box = (
        max(0, round(element.bbox.x * x_scale)),
        max(0, round(element.bbox.y * y_scale)),
        min(image.width, round((element.bbox.x + element.bbox.width) * x_scale)),
        min(image.height, round((element.bbox.y + element.bbox.height) * y_scale)),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        crop = Image.new("RGB", (1, 1), "white")
    else:
        crop = image.crop(box)
    region = crop.resize((16, 16), Image.Resampling.BILINEAR).tobytes()
    return Fingerprint(
        tag=element.tag,
        role=element.role,
        text=" ".join(element.text.casefold().split())[:160],
        region_hash=hashlib.sha256(region).hexdigest()[:16],
        phash=average_hash(crop),
    )
