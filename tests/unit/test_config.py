"""
Unit tests for configuration and small utilities
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from mocr.config import Config
from mocr.utils import WindowsIntegration

from PyQt5.QtGui import QColor


class TestConfig:
    """Test configuration settings"""

    def test_hotkey_is_defined(self):
        """Test that hotkey is configured"""
        assert hasattr(Config, 'HOTKEY')
        assert Config.HOTKEY == "ctrl+alt+prtscn"

    def test_ocr_language_is_defined(self):
        """Test that OCR language is set"""
        assert hasattr(Config, 'LANGUAGE')
        assert Config.LANGUAGE == "eng"

    def test_supported_languages_contains_english(self):
        """Test that English is in supported languages"""
        assert "English" in Config.SUPPORTED_LANGUAGES
        assert Config.SUPPORTED_LANGUAGES["English"] == "eng"

    def test_selection_color_is_valid(self):
        """Test that selection color is properly configured"""
        assert isinstance(Config.SELECTION_COLOR, QColor)
        assert Config.SELECTION_COLOR.alpha() > 0

    def test_tesseract_path_is_configured(self):
        """Test that Tesseract path is set"""
        assert hasattr(Config, 'TESSERACT_PATH')
        assert "tesseract" in Config.TESSERACT_PATH.lower()

    def test_config_supported_languages_have_codes(self):
        """Test that all supported languages have valid codes"""
        for lang_name, lang_code in Config.SUPPORTED_LANGUAGES.items():
            assert isinstance(lang_name, str)
            assert isinstance(lang_code, str)
            assert len(lang_code) > 0
            assert "_" in lang_code or len(lang_code) == 3  # Standard OCR lang codes


class TestWindowsIntegration:
    """Test Windows integration utilities"""

    def test_is_windows_returns_bool(self):
        """Test is_windows returns boolean"""
        result = WindowsIntegration.is_windows()
        assert isinstance(result, bool)
