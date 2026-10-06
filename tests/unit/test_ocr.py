"""
Unit tests for the OCR engine with Tesseract mocked out
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[2]))

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
