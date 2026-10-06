"""
Unit tests for the ScreenOCRApp controller with the tray and keyboard mocked out
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from mocr.config import Config
from mocr.utils import KEYBOARD_AVAILABLE


class TestHotkey:
    """Test hotkey configuration and polling setup"""

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

    @pytest.mark.skipif(not KEYBOARD_AVAILABLE, reason="keyboard module not available")
    def test_hotkey_polling_timer_initialization(self, ocr_app):
        """Test that hotkey polling timer is created, active and parsed"""
        assert ocr_app.hotkey_timer is not None, "Hotkey timer should be initialized"
        assert ocr_app.hotkey_timer.isActive(), "Hotkey timer should be active"
        assert ocr_app.hotkey_keys == ["ctrl", "alt", "prtscn"], "Hotkey keys should be parsed"

    @pytest.mark.skipif(not KEYBOARD_AVAILABLE, reason="keyboard module not available")
    def test_hotkey_polling_interval(self, ocr_app):
        """100ms polling interval should not noticeably lag user interaction"""
        assert ocr_app.hotkey_timer.interval() == 100, "Timer interval should be 100ms"

    def test_quit_stops_hotkey_polling(self, ocr_app, mock_tray):
        ocr_app.quit_app()
        assert ocr_app.hotkey_timer is None
        mock_tray.hide.assert_called_once()


class TestTrayMenu:
    """Test tray menu construction (tray itself is mocked)"""

    def test_tray_icon_shown_with_context_menu(self, ocr_app, mock_tray):
        mock_tray.show.assert_called_once()
        menu = mock_tray.setContextMenu.call_args.args[0]
        labels = [a.text() for a in menu.actions() if not a.isSeparator()]
        assert any("Capture" in label for label in labels)
        assert any("Exit" in label for label in labels)

    def test_show_last_result_without_result_notifies(self, ocr_app, mock_tray):
        mock_tray.showMessage.reset_mock()
        ocr_app.show_last_result()
        assert mock_tray.showMessage.call_args.args[0] == "No Result"
