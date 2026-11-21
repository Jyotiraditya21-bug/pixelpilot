from pathlib import Path

from benchmarks.run_benchmark import Score, write_results
from pytest import MonkeyPatch


def test_results_include_separate_vlm_only_rows(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    scores = {
        (runner, mutate): Score(1, 1)
        for runner in ("Scripted baseline", "PixelPilot", "PixelPilot VLM-only")
        for mutate in (False, True)
    }
    (tmp_path / "benchmarks").mkdir()
    rendered = write_results(scores, 1).read_text()
    assert "| PixelPilot VLM-only | 0 | 1/1 | 100.0% |" in rendered
    assert "| PixelPilot VLM-only | 1 | 1/1 | 100.0% |" in rendered


def test_results_include_fixtures_table(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    scores = {
        (runner, mutate): Score(1, 1)
        for runner in ("Scripted baseline", "PixelPilot", "PixelPilot VLM-only")
        for mutate in (False, True)
    }
    fixture_scores = {
        ("scroll", False, "Standard"): Score(1, 1),
        ("scroll", True, "VLM-only"): Score(0, 1),
    }
    (tmp_path / "benchmarks").mkdir()
    rendered = write_results(scores, 1, fixture_scores).read_text()
    assert "## Fixtures results" in rendered
    assert "| scroll | 0 | Standard | 1/1 | 100.0% |" in rendered
    assert "| scroll | 1 | VLM-only | 0/1 | 0.0% |" in rendered
