"""
Unit tests for ClipboardManager with Qt and win32 clipboards mocked
"""

from unittest.mock import MagicMock

from PyQt5.QtGui import QClipboard

import mocr.clipboard
from mocr.clipboard import ClipboardManager


def test_copy_text_sets_qt_and_win32(monkeypatch):
    qt_clipboard = MagicMock()
    monkeypatch.setattr(mocr.clipboard.QApplication, "clipboard", staticmethod(lambda: qt_clipboard))
    win32 = MagicMock()
    monkeypatch.setattr(mocr.clipboard, "WIN32_AVAILABLE", True)
    monkeypatch.setattr(mocr.clipboard, "win32clipboard", win32, raising=False)
    monkeypatch.setattr(mocr.clipboard, "win32con", MagicMock(CF_UNICODETEXT=13), raising=False)

    assert ClipboardManager.copy_text("hello") is True

    qt_clipboard.setText.assert_any_call("hello", QClipboard.Clipboard)
    win32.SetClipboardText.assert_called_once_with("hello", 13)
    win32.CloseClipboard.assert_called_once()


def test_win32_failure_falls_back_to_qt(monkeypatch):
    qt_clipboard = MagicMock()
    monkeypatch.setattr(mocr.clipboard.QApplication, "clipboard", staticmethod(lambda: qt_clipboard))
    win32 = MagicMock()
    win32.OpenClipboard.side_effect = RuntimeError("busy")
    monkeypatch.setattr(mocr.clipboard, "WIN32_AVAILABLE", True)
    monkeypatch.setattr(mocr.clipboard, "win32clipboard", win32, raising=False)

    assert ClipboardManager.copy_text("hello") is True
    qt_clipboard.setText.assert_any_call("hello", QClipboard.Clipboard)


def test_qt_failure_returns_false(monkeypatch):
    def broken():
        raise RuntimeError("no clipboard")
    monkeypatch.setattr(mocr.clipboard.QApplication, "clipboard", staticmethod(broken))

    assert ClipboardManager.copy_text("hello") is False


def test_get_text(monkeypatch):
    qt_clipboard = MagicMock()
    qt_clipboard.text.return_value = "abc"
    monkeypatch.setattr(mocr.clipboard.QApplication, "clipboard", staticmethod(lambda: qt_clipboard))

    assert ClipboardManager.get_text() == "abc"
