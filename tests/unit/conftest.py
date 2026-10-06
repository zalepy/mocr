"""
Unit test fixtures.

Unit tests must never interact with the OS. The autouse `forbid_os_interaction`
fixture turns every known OS touch point into a failing assertion, so a test
that forgets to mock one fails loudly instead of popping a notification or
overwriting the user's clipboard. Tests that need the real thing belong in
tests/e2e.
"""

import subprocess

import pytest
from unittest.mock import MagicMock
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QClipboard, QScreen
from PyQt5.QtWidgets import QSystemTrayIcon, QWidget, QDialog

import mocr.app
import mocr.clipboard
import mocr.hotkey
import mocr.ocr


def _forbidden(what):
    def _raise(*args, **kwargs):
        raise AssertionError(
            f"Unit test attempted OS interaction: {what}. "
            "Mock it, or move the test to tests/e2e."
        )
    return _raise


@pytest.fixture(autouse=True)
def forbid_os_interaction(monkeypatch):
    """Fail any unit test that reaches the real OS"""
    monkeypatch.setattr(QSystemTrayIcon, "show", _forbidden("showing the tray icon"))
    monkeypatch.setattr(QSystemTrayIcon, "showMessage", _forbidden("tray notification"))
    monkeypatch.setattr(QWidget, "show", _forbidden("showing a window"))
    monkeypatch.setattr(QDialog, "exec_", _forbidden("showing a modal dialog"))
    monkeypatch.setattr(QClipboard, "setText", _forbidden("writing the clipboard"))
    monkeypatch.setattr(QClipboard, "text", _forbidden("reading the clipboard"))
    monkeypatch.setattr(QScreen, "grabWindow", _forbidden("grabbing the screen"))
    monkeypatch.setattr(subprocess, "run", _forbidden("running a subprocess"))
    monkeypatch.setattr(subprocess, "Popen", _forbidden("running a subprocess"))
    if mocr.clipboard.WIN32_AVAILABLE:
        monkeypatch.setattr(mocr.clipboard.win32clipboard, "OpenClipboard",
                            _forbidden("opening the Windows clipboard"))
    if mocr.ocr.TESSERACT_AVAILABLE:
        monkeypatch.setattr(mocr.ocr.pytesseract, "image_to_string",
                            _forbidden("running Tesseract"))
        monkeypatch.setattr(mocr.ocr.pytesseract, "image_to_data",
                            _forbidden("running Tesseract"))
    # The default QSettings store is the registry (HKCU\Software\mocr)
    monkeypatch.setattr(mocr.app, "QSettings", _forbidden("using the real settings store (registry)"))
    monkeypatch.setattr(mocr.hotkey, "_user32", _forbidden("registering a global hotkey"))


@pytest.fixture
def mock_tray(monkeypatch):
    """Replace the system tray icon class used by ScreenOCRApp with a mock"""
    tray_cls = MagicMock(name="QSystemTrayIcon")
    monkeypatch.setattr(mocr.app, "QSystemTrayIcon", tray_cls)
    return tray_cls.return_value


@pytest.fixture
def settings_store(tmp_path):
    """QSettings backed by a temp INI file instead of the registry"""
    return QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)


@pytest.fixture
def ocr_app(qapp, mock_tray, settings_store, monkeypatch):
    """ScreenOCRApp instance with the tray mocked out and temp settings"""
    monkeypatch.setattr(mocr.hotkey, "_user32", MagicMock(name="user32"))
    monkeypatch.setattr(mocr.app.QApplication, "quit", MagicMock())
    # Settings changes write Config.LANGUAGE; restore it after the test
    monkeypatch.setattr(mocr.app.Config, "LANGUAGE", mocr.app.Config.LANGUAGE)
    app = mocr.app.ScreenOCRApp(settings_store=settings_store)
    yield app
    # Leave no native event filter installed on the shared QApplication
    app._unregister_hotkey()
