import io

import pytest
from PIL import Image

from pixelpilot.models import BBox, GroundingResult
from pixelpilot.vision.coords import resize_for_vlm
from pixelpilot.vision.parsing import VisionParseError, parse_json_model


def test_parser_accepts_json_fence_and_rejects_prose() -> None:
    result = parse_json_model(
        '```json\n{"bbox":{"x":10,"y":20,"width":30,"height":40},'
        '"confidence":0.9,"description":"buy"}\n```',
        GroundingResult,
    )
    assert result.bbox.center == (25, 40)
    with pytest.raises(VisionParseError):
        parse_json_model("Here is the result: {}", GroundingResult)


def test_resize_and_absolute_coordinate_conversion() -> None:
    source = Image.new("RGB", (2560, 1280), "white")
    buffer = io.BytesIO()
    source.save(buffer, "PNG")
    encoded, transform = resize_for_vlm(buffer.getvalue())
    assert Image.open(io.BytesIO(encoded)).size == (1280, 640)
    assert transform.to_source(BBox(x=100, y=50, width=200, height=100)) == BBox(
        x=200, y=100, width=400, height=200
    )


def test_parser_rejects_extra_fields() -> None:
    with pytest.raises(VisionParseError):
        parse_json_model(
            '{"bbox":{"x":0,"y":0,"width":1,"height":1},'
            '"confidence":1,"description":"x","extra":true}',
            GroundingResult,
        )
