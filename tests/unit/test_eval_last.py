"""
Unit tests for eval_last.py: strategy transforms are pure image functions;
the OCR engine is mocked.
"""

import pytest
from unittest.mock import MagicMock, patch

import numpy as np
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


class TestTransforms:

    def test_strategy_names_unique(self):
        names = [s.name for s in STRATEGIES]
        assert len(names) == len(set(names))

    @pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
    def test_every_transform_returns_image(self, strategy, text_image):
        result = strategy.transform(text_image)
        assert isinstance(result, Image.Image)
        assert result.width > 0 and result.height > 0

    def test_raw_is_unchanged(self, text_image):
        assert np.array_equal(np.array(eval_last.raw(text_image)), np.array(text_image))

    @pytest.mark.parametrize("factor,size", [(0.5, (100, 30)), (2, (400, 120)), (3, (600, 180))])
    def test_scale(self, text_image, factor, size):
        assert eval_last.scale(factor)(text_image).size == size

    def test_scale_never_zero(self):
        assert eval_last.scale(0.01)(Image.new("RGB", (10, 10))).size == (1, 1)

    def test_otsu_is_binary(self, text_image):
        values = set(np.unique(np.array(eval_last.otsu_threshold(text_image))))
        assert values <= {0, 255}

    def test_thin_strokes_reduces_dark_pixels(self, text_image):
        before = (np.array(eval_last.otsu_threshold(text_image)) == 0).sum()
        after = (np.array(eval_last.thin_strokes(text_image)) == 0).sum()
        assert 0 < after < before

    def test_thin_strokes_normalizes_light_text_to_dark(self, text_image):
        from PIL import ImageOps
        light_on_dark = ImageOps.invert(text_image)
        result = np.array(eval_last.thin_strokes(light_on_dark))
        assert result.mean() > 127  # background is light

    def test_pad_uses_edge_color(self, text_image):
        padded = eval_last.pad(text_image, border=10)
        assert padded.size == (220, 80)
        assert padded.getpixel((0, 0)) == 255

    def test_psm_strategies_carry_config(self):
        configs = {s.name: s.tesseract_config for s in STRATEGIES}
        assert configs["psm7"] == "--psm 7"
        assert configs["default"] == ""


class TestMain:

    def test_runs_all_strategies_and_saves_images(self, capture_file, tmp_path, mock_engine, capsys):
        out = tmp_path / "out"

        assert main([str(capture_file), "--out", str(out)]) == 0

        assert mock_engine.recognize.call_count == len(STRATEGIES)
        saved = sorted(p.name for p in out.iterdir())
        assert saved[0] == "01_raw.png"
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
