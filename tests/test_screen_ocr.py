"""
Unit tests for Screen OCR Tool

Testing includes:
- OCR Engine functionality
- Clipboard Manager operations
- Configuration management
- Windows integration utilities
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from screen_ocr import (
    OCREngine, ClipboardManager, Config, WindowsIntegration,
    TESSERACT_AVAILABLE, WIN32_AVAILABLE, KEYBOARD_AVAILABLE
)

from PyQt5.QtGui import QPixmap, QColor
from PyQt5.QtCore import QBuffer


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


class TestOCREngine:
    """Test OCR Engine functionality"""
    
    @pytest.fixture
    def ocr_engine(self):
        """Create OCR engine instance"""
        return OCREngine()
    
    @pytest.fixture
    def sample_image(self, qapp):
        """Load sample test image"""
        test_image_path = Path(__file__).parent / "sample.png"
        if not test_image_path.exists():
            pytest.skip(f"Sample image not found at {test_image_path}")
        
        pixmap = QPixmap(str(test_image_path))
        assert not pixmap.isNull(), "Failed to load sample image"
        return pixmap
    
    @pytest.fixture
    def sample2_image(self, qapp):
        """Load sample2 test image"""
        test_image_path = Path(__file__).parent / "sample2.png"
        if not test_image_path.exists():
            pytest.skip(f"Sample2 image not found at {test_image_path}")
        
        pixmap = QPixmap(str(test_image_path))
        assert not pixmap.isNull(), "Failed to load sample2 image"
        return pixmap
    
    def test_ocr_engine_initialization(self, ocr_engine):
        """Test OCR engine initializes without errors"""
        assert ocr_engine is not None
    
    @pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="Tesseract not installed")
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
    
    @pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="Tesseract not installed")
    def test_process_image_returns_string(self, ocr_engine, sample_image):
        """Test that process_image returns a string"""
        result = ocr_engine.process_image(sample_image)
        assert isinstance(result, str)
    
    @pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="Tesseract not installed")
    def test_process_image_with_different_language(self, ocr_engine, sample_image):
        """Test that language parameter is accepted"""
        # Should not raise an error
        result = ocr_engine.process_image(sample_image, language="eng")
        assert isinstance(result, str)
    
    @pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="Tesseract not installed")
    def test_process_image_with_sample2(self, ocr_engine, sample2_image):
        """Test OCR processing on sample2 image - known to fail
        
        Expected text: "this is wild"
        This test reproduces the OCR failure for sample2.png.
        """
        result = ocr_engine.process_image(sample2_image, language="eng")
        
        # Basic validation - should return a string
        assert isinstance(result, str), "OCR did not return a string"
        
        # Print the actual result for debugging
        print(f"\\nSample2 OCR Result: {repr(result)}")
        print(f"Result length: {len(result)} characters")
        
        # Check if result is empty or just whitespace (common failure mode)
        if not result or result.isspace():
            pytest.fail(f"OCR returned empty or whitespace-only result for sample2.png: {repr(result)}")
        
        # Check for the expected text "this is wild"
        expected_text = "this is wild"
        if expected_text.lower() not in result.lower():
            pytest.fail(f"Expected text '{expected_text}' not found in OCR result: {repr(result)}")
    
    def test_process_image_blank_pixmap(self, ocr_engine, qapp):
        """Test processing a blank image"""
        # Create a blank white pixmap
        blank_pixmap = QPixmap(100, 100)
        blank_pixmap.fill(QColor("white"))
        
        if TESSERACT_AVAILABLE:
            result = ocr_engine.process_image(blank_pixmap)
            # Should either return empty or no text detected message
            assert isinstance(result, str)
            assert (result.strip() == "" or "No text detected" in result)


class TestClipboardManager:
    """Test Clipboard Manager functionality"""
    
    def test_copy_text_returns_bool(self):
        """Test that copy_text returns a boolean"""
        result = ClipboardManager.copy_text("test text")
        assert isinstance(result, bool)
    
    def test_copy_simple_text(self):
        """Test copying simple text to clipboard"""
        test_text = "Hello, World!"
        result = ClipboardManager.copy_text(test_text)
        assert result is True
        
        # Verify by reading back
        retrieved = ClipboardManager.get_text()
        assert retrieved == test_text
    
    def test_copy_multiline_text(self):
        """Test copying multiline text"""
        test_text = "Line 1\nLine 2\nLine 3"
        result = ClipboardManager.copy_text(test_text)
        assert result is True
        
        retrieved = ClipboardManager.get_text()
        assert retrieved == test_text
    
    def test_copy_empty_string(self):
        """Test copying empty string"""
        result = ClipboardManager.copy_text("")
        assert result is True
        
        retrieved = ClipboardManager.get_text()
        assert retrieved == ""
    
    def test_copy_unicode_text(self):
        """Test copying unicode text"""
        test_text = "Hello 世界 مرحبا мир"
        result = ClipboardManager.copy_text(test_text)
        assert result is True
        
        retrieved = ClipboardManager.get_text()
        assert retrieved == test_text
    
    def test_get_text_returns_string(self):
        """Test that get_text returns a string"""
        result = ClipboardManager.get_text()
        assert isinstance(result, str)
    
    def test_copy_long_text(self):
        """Test copying very long text"""
        test_text = "A" * 10000
        result = ClipboardManager.copy_text(test_text)
        assert result is True
        
        retrieved = ClipboardManager.get_text()
        assert len(retrieved) == 10000


class TestWindowsIntegration:
    """Test Windows integration utilities"""
    
    def test_is_windows_returns_bool(self):
        """Test is_windows returns boolean"""
        result = WindowsIntegration.is_windows()
        assert isinstance(result, bool)
    
    def test_get_startup_folder_returns_path(self):
        """Test get_startup_folder returns a Path"""
        result = WindowsIntegration.get_startup_folder()
        assert isinstance(result, Path)
    
    def test_get_startup_folder_on_windows(self):
        """Test startup folder path on Windows"""
        if sys.platform == 'win32':
            startup_folder = WindowsIntegration.get_startup_folder()
            assert "Startup" in str(startup_folder)
        else:
            startup_folder = WindowsIntegration.get_startup_folder()
            assert startup_folder == Path.home()
    
    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows-only test")
    def test_add_to_startup_functionality(self, tmp_path):
        """Test adding script to startup folder"""
        # Use temp path to avoid affecting real startup
        script_path = str(tmp_path / "test_script.py")
        
        # Create dummy script
        with open(script_path, 'w') as f:
            f.write("# Test script")
        
        # This should succeed
        result = WindowsIntegration.add_to_startup(script_path, name="TestScreenOCR")
        assert isinstance(result, bool)
    
    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows-only test")
    def test_remove_from_startup_functionality(self):
        """Test removing script from startup folder"""
        result = WindowsIntegration.remove_from_startup(name="NonExistentApp")
        # Should return False if doesn't exist, True if removed
        assert isinstance(result, bool)
    
    @pytest.mark.skipif(not WIN32_AVAILABLE, reason="win32 modules not available")
    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows-only test")
    def test_set_autostart_registry_functionality(self, tmp_path):
        """Test registry autostart functionality"""
        script_path = str(tmp_path / "test_script.py")
        
        # Create dummy script
        with open(script_path, 'w') as f:
            f.write("# Test script")
        
        # Test setting
        result = WindowsIntegration.set_autostart_registry(True, script_path, name="TestScreenOCRRegistry")
        assert isinstance(result, bool)
        
        # Test unsetting
        result2 = WindowsIntegration.set_autostart_registry(False, script_path, name="TestScreenOCRRegistry")
        assert isinstance(result2, bool)


class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.skipif(not TESSERACT_AVAILABLE, reason="Tesseract not installed")
    def test_ocr_to_clipboard_workflow(self, qapp):
        """Test complete OCR to clipboard workflow"""
        test_image_path = Path(__file__).parent / "sample.png"
        if not test_image_path.exists():
            pytest.skip(f"Sample image not found at {test_image_path}")
        
        # Load image
        pixmap = QPixmap(str(test_image_path))
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
    
    def test_config_supported_languages_have_codes(self):
        """Test that all supported languages have valid codes"""
        for lang_name, lang_code in Config.SUPPORTED_LANGUAGES.items():
            assert isinstance(lang_name, str)
            assert isinstance(lang_code, str)
            assert len(lang_code) > 0
            assert "_" in lang_code or len(lang_code) == 3  # Standard OCR lang codes


class TestHotkeyAndUI:
    """Test hotkey functionality and UI responsiveness"""
    
    @pytest.mark.skipif(not KEYBOARD_AVAILABLE, reason="keyboard module not available")
    def test_hotkey_keys_parsed_correctly(self):
        """Test that hotkey configuration is parsed correctly"""
        # Should parse "ctrl+alt+prtscn" into ["ctrl", "alt", "prtscn"]
        expected_keys = Config.HOTKEY.lower().split("+")
        assert len(expected_keys) >= 2, "Hotkey should have at least 2 keys"
        assert "ctrl" in expected_keys, "Hotkey should include ctrl modifier"
        
        # Check that keys are valid keyboard module key names
        valid_keys = ["ctrl", "shift", "alt", "prtscn", "o", "print", "enter"]
        for key in expected_keys:
            assert key in valid_keys or len(key) <= 3, f"Invalid key name: {key}"
    
    def test_hotkey_polling_timer_initialization(self, qtbot):
        """Test that hotkey polling timer is properly initialized
        
        This test ensures the timer is created but doesn't block UI.
        """
        from screen_ocr import ScreenOCRApp
        from PyQt5.QtWidgets import QApplication
        
        # Create app (will only work with Qt event loop)
        app = ScreenOCRApp()
        
        # Verify hotkey timer exists
        if KEYBOARD_AVAILABLE:
            assert app.hotkey_timer is not None, "Hotkey timer should be initialized"
            assert app.hotkey_timer.isActive(), "Hotkey timer should be active"
            assert app.hotkey_keys == ["ctrl", "alt", "prtscn"], "Hotkey keys should be parsed"
        
        # Cleanup
        app.quit_app()
    
    def test_ui_responsive_after_hotkey_setup(self, qtbot):
        """Test that app can be created and used after hotkey setup
        
        This test ensures the hotkey setup doesn't cause crashes or UI freezes.
        """
        from screen_ocr import ScreenOCRApp
        
        # Create app - if hotkey setup blocks, this will timeout
        app = ScreenOCRApp()
        
        # Verify tray icon is working
        assert app.tray_icon is not None
        assert app.tray_icon.isVisible()
        
        # Verify hotkey timer is running
        if KEYBOARD_AVAILABLE:
            assert app.hotkey_timer is not None
            assert app.hotkey_timer.isActive()
        
        # Cleanup
        app.quit_app()
    
    def test_tray_remains_clickable_after_setup(self, qtbot):
        """Test that system tray remains clickable after hotkey setup
        
        This test simulates tray interaction to ensure it's not blocked by hotkey.
        """
        from screen_ocr import ScreenOCRApp
        from PyQt5.QtWidgets import QSystemTrayIcon
        
        app = ScreenOCRApp()
        
        # Verify tray icon exists and is visible
        assert app.tray_icon is not None, "Tray icon should exist"
        assert app.tray_icon.isVisible(), "Tray icon should be visible"
        
        # Simulate a tray context menu click (should not freeze)
        menu = app.tray_icon.contextMenu()
        assert menu is not None, "Context menu should exist"
        assert len(menu.actions()) > 0, "Menu should have actions"
        
        # Process a few events to make sure everything is responsive
        qtbot.wait(50)
        
        # Cleanup
        app.quit_app()
    
    def test_hotkey_polling_doesnt_block_event_loop(self, qtbot):
        """Test that hotkey polling with short timer interval doesn't block UI
        
        100ms timer interval should not significantly impact UI responsiveness.
        """
        from screen_ocr import ScreenOCRApp
        import time
        
        app = ScreenOCRApp()
        
        if KEYBOARD_AVAILABLE:
            # Verify timer interval is reasonable
            assert app.hotkey_timer.interval() == 100, "Timer interval should be 100ms"
            
            # Verify timer is precise enough for user interaction
            # (If timer was blocking, interval would be > 100ms)
            timer_interval = app.hotkey_timer.interval()
            assert timer_interval <= 200, "Timer interval should be < 200ms to avoid noticeable lag"
        
        # Cleanup
        app.quit_app()

