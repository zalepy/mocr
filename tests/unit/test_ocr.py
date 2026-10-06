"""
Unit tests for the OCR engine with Tesseract mocked out
"""

import pytest
from unittest.mock import patch


from mocr.ocr import OCREngine, TESSERACT_AVAILABLE

from PyQt5.QtGui import QPixmap, QColor

pytestmark = pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="pytesseract not installed")


class TestOCREngine:
    """Test OCR Engine logic without running Tesseract"""

    @pytest.fixture
    def ocr_engine(self):
        """Create OCR engine instance"""
        return OCREngine()

    @pytest.fixture
    def white_pixmap(self, qapp):
        pixmap = QPixmap(100, 50)
        pixmap.fill(QColor("white"))
        return pixmap

    def test_ocr_engine_initialization(self, ocr_engine):
        """Test OCR engine initializes without errors"""
        assert ocr_engine is not None

    def test_process_image_converts_pixmap_and_strips_text(self, ocr_engine, white_pixmap):
        """QPixmap is converted to a grayscale PIL image and the result is stripped"""
        with patch("mocr.ocr.pytesseract.image_to_string", return_value="  hello\n") as ocr:
            result = ocr_engine.process_image(white_pixmap, language="eng")

        assert result == "hello"
        image = ocr.call_args.args[0]
        assert image.size == (100, 50)
        assert image.mode == "L"
        assert ocr.call_args.kwargs["lang"] == "eng"

    def test_process_image_uses_config_language_by_default(self, ocr_engine, white_pixmap):
        with patch("mocr.ocr.pytesseract.image_to_string", return_value="x") as ocr:
            ocr_engine.process_image(white_pixmap)

        assert ocr.call_args.kwargs["lang"] == "eng"

    def test_process_image_no_text_detected(self, ocr_engine, white_pixmap):
        with patch("mocr.ocr.pytesseract.image_to_string", return_value="  \n"):
            result = ocr_engine.process_image(white_pixmap)

        assert result == "(No text detected in the image)"

    def test_process_image_tesseract_missing(self, ocr_engine, white_pixmap):
        import pytesseract
        with patch("mocr.ocr.pytesseract.image_to_string",
                   side_effect=pytesseract.TesseractNotFoundError()):
            result = ocr_engine.process_image(white_pixmap)

        assert result.startswith("ERROR: Tesseract OCR not found")

    def test_process_file_missing(self, ocr_engine, tmp_path):
        result = ocr_engine.process_file(str(tmp_path / "nope.png"))
        assert result.startswith("ERROR: File not found")


class TestRecognizeAndConfidence:
    """recognize() runs Tesseract on the image as-is; mean_confidence() averages word confidences"""

    @pytest.fixture
    def rgb_image(self):
        from PIL import Image
        return Image.new("RGB", (40, 20), "white")

    def test_recognize_does_not_preprocess(self, rgb_image):
        with patch("mocr.ocr.pytesseract.image_to_string", return_value="x") as ocr:
            OCREngine().recognize(rgb_image, "eng", "--psm 7")

        assert ocr.call_args.args[0] is rgb_image
        assert ocr.call_args.kwargs == {"lang": "eng", "config": "--psm 7"}

    def test_mean_confidence_ignores_empty_and_negative(self, rgb_image):
        data = {"conf": ["-1", "90", "80", "50"], "text": ["", "hello", "world", " "]}
        with patch("mocr.ocr.pytesseract.image_to_data", return_value=data):
            assert OCREngine().mean_confidence(rgb_image) == 85.0

    def test_mean_confidence_nothing_recognized(self, rgb_image):
        data = {"conf": ["-1"], "text": [""]}
        with patch("mocr.ocr.pytesseract.image_to_data", return_value=data):
            assert OCREngine().mean_confidence(rgb_image) == -1.0

    def test_mean_confidence_error(self, rgb_image):
        with patch("mocr.ocr.pytesseract.image_to_data", side_effect=RuntimeError("boom")):
            assert OCREngine().mean_confidence(rgb_image) == -1.0
