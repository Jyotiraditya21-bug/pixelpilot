from pathlib import Path

from PIL import Image

from pixelpilot.models import BBox, GroundingTier, RunRecord, StepRecord
from pixelpilot.reporting.report import generate_report


def test_report_contains_overlay_tier_evidence_and_trace(tmp_path: Path) -> None:
    image = tmp_path / "step-01.jpg"
    Image.new("RGB", (1024, 720), "white").save(image)
    record = RunRecord(
        run_id="abc",
        story="Checkout",
        trace_id="1234",
        passed=True,
        evidence="Order confirmed",
        steps=(
            StepRecord(
                number=1,
                intent="place order",
                success=True,
                tier=GroundingTier.VLM,
                healed=True,
                confidence=0.9,
                screenshot=image,
                bbox=BBox(x=10, y=20, width=30, height=40),
            ),
        ),
    )
    source = tmp_path / "run.json"
    source.write_text(record.model_dump_json())
    rendered = generate_report(source).read_text()
    assert "vlm_bbox" in rendered
    assert "healed cache hit" in rendered
    assert "Order confirmed" in rendered
    assert "1234" in rendered
    assert 'class="bbox"' in rendered
