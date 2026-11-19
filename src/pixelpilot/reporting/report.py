from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image

from pixelpilot.models import RunRecord


def generate_report(run_json: Path) -> Path:
    run = RunRecord.model_validate_json(run_json.read_text())
    steps: list[dict[str, object]] = []
    for step in run.steps:
        image_path = step.screenshot
        overlay: dict[str, float] | None = None
        if image_path and image_path.exists() and step.bbox:
            with Image.open(image_path) as image:
                x_scale = image.width / 1280
                y_scale = image.height / 900
            overlay = {
                "x": step.bbox.x * x_scale,
                "y": step.bbox.y * y_scale,
                "width": step.bbox.width * x_scale,
                "height": step.bbox.height * y_scale,
            }
        steps.append(
            {
                "record": step,
                "tier": step.tier.value if step.tier else "direct",
                "image": image_path.name if image_path else None,
                "overlay": overlay,
            }
        )
    template_dir = Path(__file__).with_name("templates")
    environment = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(("html", "xml")),
    )
    rendered = environment.get_template("report.html.j2").render(run=run, steps=steps)
    output = run_json.with_name("report.html")
    output.write_text(rendered)
    return output
