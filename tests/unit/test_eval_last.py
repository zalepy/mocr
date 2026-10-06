"""
Unit tests for eval_last.py (the CLI); the OCR engine is mocked.
The shared transforms are tested in test_preprocess.py.
"""

import pytest
from unittest.mock import MagicMock, patch

from PIL import Image, ImageDraw

import eval_last
from eval_last import STRATEGIES, main


@pytest.fixture
def text_image():
    """Black bold-ish text on white, 200x60"""
    img = Image.new("RGB", (200, 60), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 15, 180, 45], outline="black", width=6)
    return img


@pytest.fixture
def capture_file(tmp_path, text_image):
    path = tmp_path / "capture.png"
    text_image.save(path)
    return path


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.recognize.return_value = "Detected OCR Text"
    engine.mean_confidence.return_value = 87.0
    with patch.object(eval_last, "OCREngine", return_value=engine):
        yield engine


class TestStrategies:

    def test_includes_app_strategies_plus_eval_only(self):
        from mocr.preprocess import STRATEGIES as APP_STRATEGIES
        names = [s.name for s in STRATEGIES]
        assert names[:len(APP_STRATEGIES)] == [s.name for s in APP_STRATEGIES]
        assert "edges" in names
        assert len(names) == len(set(names))

    def test_edges_returns_image(self, text_image):
        pytest.importorskip("cv2")
        result = eval_last.edge_detection(text_image)
        assert result.size == text_image.size


class TestMain:

    def test_runs_all_strategies_and_saves_images(self, capture_file, tmp_path, mock_engine, capsys):
        out = tmp_path / "out"

        assert main([str(capture_file), "--out", str(out)]) == 0

        assert mock_engine.recognize.call_count == len(STRATEGIES)
        saved = sorted(p.name for p in out.iterdir())
        assert saved[0] == "01_auto_scale.png"
        assert len(saved) == len(STRATEGIES)
        output = capsys.readouterr().out
        assert "transform failed" not in output
        assert "Detected OCR Text" in output
        assert "Processing:" in output
        assert "Summary" in output

    def test_strategy_image_goes_to_tesseract_as_is(self, capture_file, tmp_path, mock_engine):
        main([str(capture_file), "--out", str(tmp_path / "out"), "--only", "raw,psm7"])

        calls = mock_engine.recognize.call_args_list
        assert len(calls) == 2
        raw_image = calls[0].args[0]
        assert raw_image.mode == "RGB"  # not grayscaled/sharpened by the engine
        assert calls[1].args[2] == "--psm 7"

    def test_only_unknown_strategy(self, capture_file, mock_engine, capsys):
        assert main([str(capture_file), "--only", "nope"]) == 2
        assert "Unknown strategies: nope" in capsys.readouterr().out

    def test_list(self, capsys):
        assert main(["--list"]) == 0
        assert "downscale_50" in capsys.readouterr().out

    def test_missing_file(self, tmp_path, capsys):
        assert main([str(tmp_path / "missing.png")]) == 1
        assert "Error: image not found" in capsys.readouterr().out

    def test_failure_marked(self, capture_file, tmp_path, mock_engine, capsys):
        mock_engine.recognize.return_value = "(No text detected in the image)"
        mock_engine.mean_confidence.return_value = -1.0

        main([str(capture_file), "--out", str(tmp_path / "out"), "--only", "raw"])

        assert "RESULT: (FAILED/EMPTY)" in capsys.readouterr().out
