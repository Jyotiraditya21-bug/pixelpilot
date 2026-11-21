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
