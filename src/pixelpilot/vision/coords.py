from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image

from pixelpilot.models import BBox


@dataclass(frozen=True)
class ImageTransform:
    source_width: int
    source_height: int
    resized_width: int
    resized_height: int

    def to_source(self, bbox: BBox) -> BBox:
        x_scale = self.source_width / self.resized_width
        y_scale = self.source_height / self.resized_height
        return BBox(
            x=bbox.x * x_scale,
            y=bbox.y * y_scale,
            width=bbox.width * x_scale,
            height=bbox.height * y_scale,
        )


def resize_for_vlm(image_bytes: bytes, max_side: int = 1280) -> tuple[bytes, ImageTransform]:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    source_width, source_height = image.size
    if source_width <= 0 or source_height <= 0:
        raise ValueError("image dimensions must be positive")
    scale = min(1.0, max_side / max(source_width, source_height))
    resized = (max(1, round(source_width * scale)), max(1, round(source_height * scale)))
    if resized != image.size:
        image = image.resize(resized, Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, "JPEG", quality=75, optimize=True)
    transform = ImageTransform(source_width, source_height, image.width, image.height)
    return output.getvalue(), transform


def box_2d_to_viewport(
    box_2d: tuple[float, float, float, float], viewport_width: int, viewport_height: int
) -> BBox:
    vw = max(1, viewport_width)
    vh = max(1, viewport_height)
    ymin, xmin, ymax, xmax = (min(1000.0, max(0.0, value)) for value in box_2d)
    left, right = sorted((xmin, xmax))
    top, bottom = sorted((ymin, ymax))
    return BBox(
        x=left * vw / 1000,
        y=top * vh / 1000,
        width=(right - left) * vw / 1000,
        height=(bottom - top) * vh / 1000,
    )
