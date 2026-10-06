"""
Unit tests for mocr.preprocess: pure image transforms, no OCR involved.
Synthetic images stand in for text: dark bars of a known height on a light background.
"""

import pytest
from PIL import Image, ImageDraw, ImageOps

from mocr import preprocess
from mocr.preprocess import (
    STRATEGIES, STRATEGIES_BY_NAME, TARGET_LINE_HEIGHT,
    auto_scale, auto_scale_factor, estimate_line_height, otsu_level,
)


def lines_image(line_height, lines=3, gap=None, width=300, dark_on_light=True):
    """`lines` dark bars of `line_height` px, separated by `gap` px"""
    gap = gap if gap is not None else line_height
    height = lines * (line_height + gap) + gap
    bg, fg = ("white", "black") if dark_on_light else ("black", "white")
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    y = gap
    for _ in range(lines):
        draw.rectangle([10, y, width - 10, y + line_height - 1], fill=fg)
        y += line_height + gap
    return img


def dark_pixels(img):
    return ImageOps.grayscale(img).histogram()[0]


@pytest.fixture
def text_image():
    """Black bold-ish outline on white, 200x60"""
    img = Image.new("RGB", (200, 60), "white")
    ImageDraw.Draw(img).rectangle([20, 15, 180, 45], outline="black", width=6)
    return img


class TestLineHeight:

    @pytest.mark.parametrize("height", [8, 19, 40, 120])
    def test_measures_line_height(self, height):
        assert estimate_line_height(lines_image(height)) == height

    def test_light_text_on_dark(self):
        assert estimate_line_height(lines_image(25, dark_on_light=False)) == 25

    def test_median_ignores_outlier_line(self):
        img = lines_image(20, lines=4)
        ImageDraw.Draw(img).rectangle([10, 0, 290, 1], fill="black")  # 2 px rule at the top
        assert estimate_line_height(img) == 20

    def test_blank_image(self):
        assert estimate_line_height(Image.new("RGB", (100, 50), "white")) is None


class TestAutoScale:

    def test_small_text_is_upscaled_without_sharpen(self):
        img = lines_image(10)
        assert auto_scale_factor(img) == pytest.approx(TARGET_LINE_HEIGHT / 10)
        result = auto_scale(img)
        assert result.height == round(img.height * TARGET_LINE_HEIGHT / 10)
        # Not sharpened: same as a plain resize
        plain = preprocess._resize(ImageOps.grayscale(img), TARGET_LINE_HEIGHT / 10)
        assert result.tobytes() == plain.tobytes()

    def test_large_text_is_downscaled(self):
        img = lines_image(88)
        assert auto_scale_factor(img) == pytest.approx(0.25)
        assert auto_scale(img).height == round(img.height * 0.25)

    def test_huge_text_is_clamped(self):
        assert auto_scale_factor(lines_image(400, lines=1)) == preprocess.MIN_SCALE

    def test_tiny_text_is_clamped(self):
        assert auto_scale_factor(lines_image(3)) == preprocess.MAX_SCALE

    def test_close_to_target_is_left_alone(self):
        img = lines_image(TARGET_LINE_HEIGHT + 2)
        assert auto_scale_factor(img) == 1.0
        assert auto_scale(img).size == img.size

    def test_no_text_is_left_alone(self):
        img = Image.new("RGB", (100, 50), "white")
        assert auto_scale_factor(img) == 1.0
        assert auto_scale(img).mode == "L"


class TestTransforms:

    def test_strategy_names_unique_and_indexed(self):
        names = [s.name for s in STRATEGIES]
        assert len(names) == len(set(names))
        assert set(STRATEGIES_BY_NAME) == set(names)

    @pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
    def test_every_transform_returns_image(self, strategy, text_image):
        result = strategy.transform(text_image)
        assert isinstance(result, Image.Image)
        assert result.width > 0 and result.height > 0

    def test_raw_is_unchanged(self, text_image):
        assert preprocess.raw(text_image).tobytes() == text_image.tobytes()

    def test_default_is_grayscale(self, text_image):
        assert preprocess.default(text_image).mode == "L"

    @pytest.mark.parametrize("factor,size", [(0.5, (100, 30)), (2, (400, 120)), (3, (600, 180))])
    def test_scale(self, text_image, factor, size):
        assert preprocess.scale(factor)(text_image).size == size

    def test_scale_never_zero(self):
        assert preprocess.scale(0.01)(Image.new("RGB", (10, 10))).size == (1, 1)

    def test_otsu_level_splits_two_tones(self):
        img = Image.new("L", (10, 10), 40)
        ImageDraw.Draw(img).rectangle([0, 0, 4, 9], fill=200)
        assert 40 <= otsu_level(img) < 200

    def test_otsu_is_binary(self, text_image):
        colors = {c for _, c in preprocess.otsu_threshold(text_image).getcolors()}
        assert colors <= {0, 255}

    def test_thin_strokes_reduces_dark_pixels(self, text_image):
        before = dark_pixels(preprocess.otsu_threshold(text_image))
        after = dark_pixels(preprocess.thin_strokes(text_image))
        assert 0 < after < before

    def test_thin_strokes_normalizes_light_text_to_dark(self, text_image):
        result = preprocess.thin_strokes(ImageOps.invert(text_image))
        assert dark_pixels(result) < result.width * result.height / 2  # background is light

    def test_pad_uses_edge_color(self, text_image):
        padded = preprocess.pad(text_image, border=10)
        assert padded.size == (220, 80)
        assert padded.getpixel((0, 0)) == 255

    def test_otsu_level_low_splits_bright_classes(self):
        img = Image.new("L", (30, 10), 0)            # black photo strip
        ImageDraw.Draw(img).rectangle([10, 0, 29, 9], fill=140)  # blue band
        ImageDraw.Draw(img).rectangle([20, 0, 29, 9], fill=250)  # white text
        assert otsu_level(img) < 140
        assert 140 <= otsu_level(img, low=otsu_level(img)) < 250

    def test_light_text_keeps_only_brightest_as_dark_text(self):
        img = Image.new("RGB", (300, 120), (0, 0, 0))                   # dark photo
        ImageDraw.Draw(img).rectangle([0, 0, 299, 80], fill=(40, 170, 250))  # blue band
        ImageDraw.Draw(img).rectangle([20, 30, 280, 50], fill="white")      # "text" line
        result = preprocess.light_text(img)
        # Only the white bar is dark; band and photo became background
        assert result.size == img.size  # 20 px line: already near target
        assert dark_pixels(result) == 261 * 21

    def test_psm_strategies_carry_config(self):
        assert STRATEGIES_BY_NAME["psm7"].tesseract_config == "--psm 7"
        assert STRATEGIES_BY_NAME["default"].tesseract_config == ""
