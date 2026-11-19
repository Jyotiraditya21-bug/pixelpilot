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
    scale = min(1.0, max_side / max(image.size))
    resized = (round(source_width * scale), round(source_height * scale))
    if resized != image.size:
        image = image.resize(resized, Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, "JPEG", quality=75, optimize=True)
    transform = ImageTransform(source_width, source_height, image.width, image.height)
    return output.getvalue(), transform
