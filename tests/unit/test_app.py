"""
Unit tests for the ScreenOCRApp controller with the tray and hotkey mocked out
"""

import pytest
from unittest.mock import MagicMock

import mocr.hotkey
from mocr.config import Config


class TestHotkey:
    """Hotkey wiring (the ocr_app fixture mocks the Win32 calls)"""

    def test_hotkey_registered_from_config(self, ocr_app):
        assert ocr_app.hotkey.text == Config.HOTKEY
        assert ocr_app.hotkey.registered

    def test_hotkey_starts_capture(self, qapp, mock_tray, settings_store, monkeypatch):
        import mocr.app
        # Patch before construction: the signal connects to the bound method
        start_capture = MagicMock()
        monkeypatch.setattr(mocr.app.ScreenOCRApp, "start_capture", start_capture)
        monkeypatch.setattr(mocr.hotkey, "_user32", MagicMock(name="user32"))
        app = mocr.app.ScreenOCRApp(settings_store=settings_store)
        try:
            app.hotkey.activated.emit()
            start_capture.assert_called_once()
        finally:
            app._unregister_hotkey()

    def test_registration_failure_warns(self, qapp, mock_tray, settings_store, monkeypatch):
        import mocr.app
        user32 = MagicMock(name="user32")
        user32.RegisterHotKey.return_value = 0  # e.g. taken by another application
        monkeypatch.setattr(mocr.hotkey, "_user32", lambda: user32)
        app = mocr.app.ScreenOCRApp(settings_store=settings_store)
        assert not app.hotkey.registered
        titles = [c.args[0] for c in mock_tray.showMessage.call_args_list]
        assert "Hotkey Unavailable" in titles

    def test_quit_unregisters_hotkey(self, ocr_app, mock_tray):
        ocr_app.quit_app()
        assert not ocr_app.hotkey.registered
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


class TestSettingsPersistence:
    """Settings survive a restart (temp INI store, never the registry)"""

    def test_defaults_when_nothing_stored(self, ocr_app):
        assert ocr_app.settings["language"] == "eng"
        assert ocr_app.settings["auto_copy"] is True
        assert ocr_app.settings["show_dialog"] is False
        assert ocr_app.settings["show_notifications"] is False

    def test_changes_survive_restart(self, ocr_app, settings_store, mock_tray):
        import mocr.app
        ocr_app._on_settings_changed({"language": "deu", "auto_copy": False,
                                      "show_dialog": True, "show_notifications": True})
        ocr_app._unregister_hotkey()

        restarted = mocr.app.ScreenOCRApp(settings_store=settings_store)
        try:
            assert restarted.settings["language"] == "deu"
            assert restarted.settings["auto_copy"] is False
            assert restarted.settings["show_dialog"] is True
            assert restarted.settings["show_notifications"] is True
            assert mocr.app.Config.LANGUAGE == "deu"
        finally:
            restarted._unregister_hotkey()

    def test_unsupported_stored_language_falls_back(self, qapp, mock_tray, settings_store, monkeypatch):
        import mocr.app
        monkeypatch.setattr(mocr.app.Config, "LANGUAGE", "eng")
        monkeypatch.setattr(mocr.hotkey, "_user32", MagicMock(name="user32"))
        settings_store.setValue("language", "klingon")
        app = mocr.app.ScreenOCRApp(settings_store=settings_store)
        try:
            assert app.settings["language"] == "eng"
        finally:
            app._unregister_hotkey()
