"""
E2E tests for the real system tray icon and hotkey polling.

These show the tray icon and its "started" notification.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from mocr.utils import KEYBOARD_AVAILABLE


class TestHotkeyAndUI:
    """Test hotkey functionality and UI responsiveness"""

    def test_ui_responsive_after_hotkey_setup(self, qtbot):
        """Test that app can be created and used after hotkey setup

        This test ensures the hotkey setup doesn't cause crashes or UI freezes.
        """
        from mocr.app import ScreenOCRApp

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
        from mocr.app import ScreenOCRApp

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
