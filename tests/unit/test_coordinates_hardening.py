from __future__ import annotations

import io

import pytest
from PIL import Image

from pixelpilot.models import BBox
from pixelpilot.vision.coords import box_2d_to_viewport, resize_for_vlm


@pytest.mark.parametrize(
    ("vw", "vh", "box_2d", "expected_bbox"),
    [
        # Standard Desktop (1920x1080)
        (1920, 1080, (100, 200, 500, 600), BBox(x=384.0, y=108.0, width=768.0, height=432.0)),
        # MacBook (1440x900)
        (1440, 900, (200, 250, 400, 750), BBox(x=360.0, y=180.0, width=720.0, height=180.0)),
        # WXGA (1280x800)
        (1280, 800, (0, 0, 1000, 1000), BBox(x=0.0, y=0.0, width=1280.0, height=800.0)),
        # Mobile (390x844)
        (390, 844, (100, 100, 200, 900), BBox(x=39.0, y=84.4, width=312.0, height=84.4)),
        # SVGA (800x600)
        (800, 600, (500, 500, 1000, 1000), BBox(x=400.0, y=300.0, width=400.0, height=300.0)),
    ],
)
def test_box_2d_converts_correctly_at_several_viewport_sizes(
    vw: int, vh: int, box_2d: tuple[float, float, float, float], expected_bbox: BBox
) -> None:
    result = box_2d_to_viewport(box_2d, vw, vh)
    assert result.x == pytest.approx(expected_bbox.x)
    assert result.y == pytest.approx(expected_bbox.y)
    assert result.width == pytest.approx(expected_bbox.width)
    assert result.height == pytest.approx(expected_bbox.height)


def test_box_2d_zero_area_boxes() -> None:
    vw, vh = 1000, 1000

    # Point box (width=0, height=0)
    point_bbox = box_2d_to_viewport((300, 400, 300, 400), vw, vh)
    assert point_bbox == BBox(x=400.0, y=300.0, width=0.0, height=0.0)
    assert point_bbox.center == (400.0, 300.0)

    # Horizontal line (zero height, non-zero width)
    h_line = box_2d_to_viewport((250, 100, 250, 900), vw, vh)
    assert h_line == BBox(x=100.0, y=250.0, width=800.0, height=0.0)

    # Vertical line (zero width, non-zero height)
    v_line = box_2d_to_viewport((100, 450, 900, 450), vw, vh)
    assert v_line == BBox(x=450.0, y=100.0, width=0.0, height=800.0)


def test_box_2d_out_of_bounds_and_inverted_coordinates() -> None:
    vw, vh = 1000, 500

    # Negative coordinates clamped to 0
    neg_bbox = box_2d_to_viewport((-200, -300, 500, 600), vw, vh)
    assert neg_bbox == BBox(x=0.0, y=0.0, width=600.0, height=250.0)

    # Over 1000 coordinates clamped to 1000
    huge_bbox = box_2d_to_viewport((500, 600, 1500, 2000), vw, vh)
    assert huge_bbox == BBox(x=600.0, y=250.0, width=400.0, height=250.0)

    # Completely out of bounds (all negative) -> zero area at (0, 0)
    all_neg = box_2d_to_viewport((-500, -400, -300, -200), vw, vh)
    assert all_neg == BBox(x=0.0, y=0.0, width=0.0, height=0.0)

    # Completely out of bounds (all > 1000) -> zero area at (vw, vh)
    all_over = box_2d_to_viewport((1200, 1300, 1400, 1500), vw, vh)
    assert all_over == BBox(x=1000.0, y=500.0, width=0.0, height=0.0)

    # Inverted coordinates (ymin > ymax, xmin > xmax) sorted properly
    inverted = box_2d_to_viewport((800, 900, 200, 100), vw, vh)
    assert inverted == BBox(x=100.0, y=100.0, width=800.0, height=300.0)


def _png_bytes(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height), "blue")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_resize_for_vlm_edge_cases() -> None:
    # 1. Image already smaller than max_side (1280): no downscale
    small_bytes = _png_bytes(640, 480)
    out_bytes, transform = resize_for_vlm(small_bytes, max_side=1280)
    assert transform.source_width == 640
    assert transform.source_height == 480
    assert transform.resized_width == 640
    assert transform.resized_height == 480
    assert transform.to_source(BBox(x=10, y=10, width=50, height=50)) == BBox(
        x=10, y=10, width=50, height=50
    )

    # 2. 1x1 image
    tiny_bytes = _png_bytes(1, 1)
    out_bytes, transform = resize_for_vlm(tiny_bytes, max_side=1280)
    assert transform.resized_width == 1
    assert transform.resized_height == 1

    # 3. Extreme aspect ratio: 10000x1 (ultra-wide)
    wide_bytes = _png_bytes(10000, 1)
    out_bytes, transform = resize_for_vlm(wide_bytes, max_side=1280)
    assert transform.resized_width == 1280
    assert transform.resized_height >= 1  # Guarded against 0 height

    # 4. Extreme aspect ratio: 1x10000 (ultra-tall)
    tall_bytes = _png_bytes(1, 10000)
    out_bytes, transform = resize_for_vlm(tall_bytes, max_side=1280)
    assert transform.resized_width >= 1  # Guarded against 0 width
    assert transform.resized_height == 1280

    # 5. 4K image (3840x2160)
    k4_bytes = _png_bytes(3840, 2160)
    out_bytes, transform = resize_for_vlm(k4_bytes, max_side=1280)
    assert transform.resized_width == 1280
    assert transform.resized_height == 720
    # Transform maps bbox on resized back to original 4K source coordinates
    resized_box = BBox(x=128.0, y=72.0, width=256.0, height=144.0)
    orig_box = transform.to_source(resized_box)
    assert orig_box == BBox(x=384.0, y=216.0, width=768.0, height=432.0)
