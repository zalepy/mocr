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
from PyQt5.QtGui import QClipboard, QScreen
from PyQt5.QtWidgets import QSystemTrayIcon, QWidget, QDialog

import mocr.app
import mocr.clipboard
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
    if mocr.app.keyboard is not None:
        monkeypatch.setattr(mocr.app.keyboard, "is_pressed",
                            _forbidden("reading global keyboard state"))


@pytest.fixture
def mock_tray(monkeypatch):
    """Replace the system tray icon class used by ScreenOCRApp with a mock"""
    tray_cls = MagicMock(name="QSystemTrayIcon")
    monkeypatch.setattr(mocr.app, "QSystemTrayIcon", tray_cls)
    return tray_cls.return_value


@pytest.fixture
def ocr_app(qapp, mock_tray, monkeypatch):
    """ScreenOCRApp instance with the tray mocked out"""
    monkeypatch.setattr(mocr.app.QApplication, "quit", MagicMock())
    app = mocr.app.ScreenOCRApp()
    yield app
    app._stop_hotkey_polling()
