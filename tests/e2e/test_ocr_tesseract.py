"""
E2E tests for OCR using the real Tesseract binary and sample images
"""

import pytest


from mocr.ocr import OCREngine, TESSERACT_AVAILABLE
from mocr.clipboard import ClipboardManager

from PyQt5.QtGui import QPixmap, QColor

pytestmark = pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="Tesseract not installed")


class TestOCREngine:
    """Test OCR Engine against real images"""

    @pytest.fixture
    def ocr_engine(self):
        """Create OCR engine instance"""
        return OCREngine()

    @pytest.fixture
    def sample_image(self, qapp, sample_image_path):
        """Load sample test image"""
        pixmap = QPixmap(str(sample_image_path))
        assert not pixmap.isNull(), "Failed to load sample image"
        return pixmap

    @pytest.fixture
    def sample2_image(self, qapp, sample2_image_path):
        """Load sample2 test image"""
        pixmap = QPixmap(str(sample2_image_path))
        assert not pixmap.isNull(), "Failed to load sample2 image"
        return pixmap

    def test_process_image_with_sample(self, ocr_engine, sample_image):
        """Test OCR processing on sample image with strict validation

        Expected text: "Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki"
        """
        result = ocr_engine.process_image(sample_image, language="eng")

        # Strict validation 1: Should not be an error
        assert not result.startswith("ERROR"), f"OCR failed: {result}"

        # Strict validation 2: Result must be non-empty and reasonable length
        assert len(result) > 0, "OCR returned empty string"
        assert len(result) > 30, f"OCR result too short ({len(result)} chars): {result}"

        # Strict validation 3: Check for complete expected text with exact phrase
        expected_phrase = "Download the installer from"
        assert expected_phrase in result, f"Expected phrase '{expected_phrase}' not found in: {result}"

        # Strict validation 4: Verify URL components are present
        assert "https://" in result or "http://" in result, f"No URL protocol found in: {result}"
        assert "github" in result.lower(), f"'github' domain not found in: {result}"
        assert "tesseract" in result.lower(), f"'tesseract' not found in: {result}"
        assert "wiki" in result.lower(), f"'wiki' not found in: {result}"

        # Strict validation 5: Verify it's not just whitespace/garbage
        assert result.strip() == result, "Result has leading/trailing whitespace"
        assert not result.isspace(), "Result is only whitespace"

        # Strict validation 6: Check that the result looks like actual text
        word_count = len(result.split())
        assert word_count >= 5, f"Result has too few words ({word_count}), likely not valid OCR"

        # Strict validation 7: Optionally check for complete URL if identifiable
        # (OCR may add spaces or slight variations, so we just check components)
        url_indicators = ["github.com", "ubmannheim", "tesseract"]
        found_url_parts = sum(1 for indicator in url_indicators if indicator.lower() in result.lower())
        assert found_url_parts >= 2, f"Less than 2 URL components found in: {result}"

    def test_process_image_returns_string(self, ocr_engine, sample_image):
        """Test that process_image returns a string"""
        result = ocr_engine.process_image(sample_image)
        assert isinstance(result, str)

    def test_process_image_with_different_language(self, ocr_engine, sample_image):
        """Test that language parameter is accepted"""
        # Should not raise an error
        result = ocr_engine.process_image(sample_image, language="eng")
        assert isinstance(result, str)

    def test_process_image_with_sample2(self, ocr_engine, sample2_image):
        """Test OCR processing on sample2 image (used to fail; kept as a regression test)

        Expected text: "this is wild"
        """
        result = ocr_engine.process_image(sample2_image, language="eng")

        # Basic validation - should return a string
        assert isinstance(result, str), "OCR did not return a string"

        # Print the actual result for debugging
        print(f"\nSample2 OCR Result: {repr(result)}")
        print(f"Result length: {len(result)} characters")

        # Check if result is empty or just whitespace (common failure mode)
        if not result or result.isspace():
            pytest.fail(f"OCR returned empty or whitespace-only result for sample2.png: {repr(result)}")

        # Check for the expected text "this is wild"
        expected_text = "this is wild"
        if expected_text.lower() not in result.lower():
            pytest.fail(f"Expected text '{expected_text}' not found in OCR result: {repr(result)}")

    @pytest.mark.parametrize("sample, factor, expected", [
        ("sample_image_path", 2, "Download the installer"),
        ("sample_image_path", 0.5, "Download the installer"),
        ("sample2_image_path", 2, "this is wild"),
    ])
    def test_auto_scale_handles_text_size(self, ocr_engine, request, sample, factor, expected):
        """The same text rendered bigger/smaller (e.g. 200% display scaling) is still read.
        At 2x the old default (grayscale + sharpen) detected nothing at all."""
        from PIL import Image
        img = Image.open(request.getfixturevalue(sample)).convert("RGB")
        img = img.resize((round(img.width * factor), round(img.height * factor)), Image.LANCZOS)

        result = ocr_engine.process_pil_image(img, "eng", "auto_scale")

        assert expected.lower() in result.lower(), repr(result)

    def test_light_text_on_busy_background(self, ocr_engine, sample3_image_path):
        """White heading on a blue band over a dark photo: every other strategy
        reads nothing; light_text isolates the brightest class"""
        result = ocr_engine.process_file(str(sample3_image_path), "eng", "light_text")
        # "AI" and "Al" are indistinguishable in this sans-serif font
        assert result.lower().replace("al ", "ai ") == "huge ai news", repr(result)

    def test_process_image_blank_pixmap(self, ocr_engine, qapp):
        """Test processing a blank image"""
        # Create a blank white pixmap
        blank_pixmap = QPixmap(100, 100)
        blank_pixmap.fill(QColor("white"))

        result = ocr_engine.process_image(blank_pixmap)
        # Should either return empty or no text detected message
        assert isinstance(result, str)
        assert (result.strip() == "" or "No text detected" in result)


class TestIntegration:
    """Integration tests"""

    def test_ocr_to_clipboard_workflow(self, qapp, sample_image_path, preserve_clipboard):
        """Test complete OCR to clipboard workflow"""
        # Load image
        pixmap = QPixmap(str(sample_image_path))
        assert not pixmap.isNull()

        # Process with OCR
        ocr_engine = OCREngine()
        ocr_text = ocr_engine.process_image(pixmap)
        assert not ocr_text.startswith("ERROR")
        assert "Download the installer from" in ocr_text

        # Copy to clipboard
        success = ClipboardManager.copy_text(ocr_text)
        assert success is True

        # Verify clipboard
        retrieved = ClipboardManager.get_text()
        assert retrieved == ocr_text
