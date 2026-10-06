"""
Unit tests for the global hotkey: parsing and WM_HOTKEY handling.
RegisterHotKey/UnregisterHotKey are mocked; no hotkey is registered with Windows.
"""

import ctypes
import ctypes.wintypes

import pytest
from unittest.mock import MagicMock

import mocr.hotkey
from mocr.hotkey import (
    GlobalHotkey, parse_hotkey, WM_HOTKEY,
    MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT,
)


class TestParseHotkey:

    @pytest.mark.parametrize("text, expected", [
        ("ctrl+alt+prtscn", (MOD_CONTROL | MOD_ALT, 0x2C)),
        ("Ctrl + Shift + PrintScreen", (MOD_CONTROL | MOD_SHIFT, 0x2C)),
        ("win+shift+o", (MOD_WIN | MOD_SHIFT, ord("O"))),
        ("alt+5", (MOD_ALT, ord("5"))),
        ("ctrl+f12", (MOD_CONTROL, 0x7B)),
        ("pause", (0, 0x13)),
    ])
    def test_valid(self, text, expected):
        assert parse_hotkey(text) == expected

    @pytest.mark.parametrize("text", [
        "ctrl+alt",          # no key
        "ctrl+a+b",          # two keys
        "ctrl+nosuchkey",
        "",
    ])
    def test_invalid(self, text):
        with pytest.raises(ValueError):
            parse_hotkey(text)


@pytest.fixture
def user32(monkeypatch):
    mock = MagicMock(name="user32")
    mock.RegisterHotKey.return_value = 1
    monkeypatch.setattr(mocr.hotkey, "_user32", lambda: mock)
    return mock


@pytest.fixture
def hotkey(qapp, user32):
    hk = GlobalHotkey("ctrl+alt+prtscn", hotkey_id=7)
    yield hk
    hk.unregister()


def send(hk, message, wparam):
    """Feed a native MSG through the hotkey's event filter, as Qt's dispatcher would"""
    msg = ctypes.wintypes.MSG()
    msg.message = message
    msg.wParam = wparam
    return hk._filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))


@pytest.mark.skipif(not hasattr(ctypes, "windll"), reason="Windows only")
class TestGlobalHotkey:

    def test_register_passes_parsed_combo(self, hotkey, user32):
        assert hotkey.register()
        user32.RegisterHotKey.assert_called_once_with(
            None, 7, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x2C)
        assert hotkey.registered

    def test_register_twice_is_noop(self, hotkey, user32):
        hotkey.register()
        hotkey.register()
        user32.RegisterHotKey.assert_called_once()

    def test_register_failure(self, hotkey, user32):
        user32.RegisterHotKey.return_value = 0
        assert not hotkey.register()
        assert not hotkey.registered
        assert hotkey._filter is None

    def test_invalid_hotkey_does_not_register(self, qapp, user32):
        assert not GlobalHotkey("ctrl+nosuchkey").register()
        user32.RegisterHotKey.assert_not_called()

    def test_wm_hotkey_emits_activated(self, hotkey):
        hotkey.register()
        hits = []
        hotkey.activated.connect(lambda: hits.append(True))

        assert send(hotkey, WM_HOTKEY, 7) == (True, 0)
        assert hits == [True]

    def test_other_messages_pass_through(self, hotkey):
        hotkey.register()
        hits = []
        hotkey.activated.connect(lambda: hits.append(True))

        assert send(hotkey, WM_HOTKEY, 8) == (False, 0)   # someone else's hotkey id
        assert send(hotkey, 0x0100, 7) == (False, 0)      # WM_KEYDOWN
        assert hits == []

    def test_unregister(self, hotkey, user32):
        hotkey.register()
        hotkey.unregister()
        user32.UnregisterHotKey.assert_called_once_with(None, 7)
        assert not hotkey.registered
        assert hotkey._filter is None
