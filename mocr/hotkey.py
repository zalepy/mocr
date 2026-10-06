"""
System-wide hotkey via the Win32 RegisterHotKey API.

Windows posts WM_HOTKEY to this thread's message queue, and a Qt native event
filter turns it into a signal. Unlike polling key state, this needs no admin
rights and sees PrtScn, which never reports a normal "held" key-down.
"""

import ctypes
import ctypes.wintypes
import sys

from PyQt5.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, pyqtSignal

from .utils import debug_print

WM_HOTKEY = 0x0312

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000  # Holding the combo fires once

MODIFIERS = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
}

NAMED_KEYS = {
    "prtscn": 0x2C, "printscreen": 0x2C, "print": 0x2C, "snapshot": 0x2C,
    "pause": 0x13, "insert": 0x2D, "ins": 0x2D, "space": 0x20,
    "scrolllock": 0x91,
    **{f"f{n}": 0x6F + n for n in range(1, 25)},  # F1 = 0x70
}


def parse_hotkey(text: str) -> tuple[int, int]:
    """
    Parse "ctrl+alt+prtscn" into (modifier flags, virtual-key code).

    Exactly one non-modifier key is allowed. Raises ValueError otherwise.
    """
    mods = 0
    vk = None
    for part in (p.strip().lower() for p in text.split("+")):
        if part in MODIFIERS:
            mods |= MODIFIERS[part]
        elif vk is not None:
            raise ValueError(f"Hotkey {text!r} has more than one non-modifier key")
        elif part in NAMED_KEYS:
            vk = NAMED_KEYS[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())  # VK codes for A-Z / 0-9 are their ASCII
        else:
            raise ValueError(f"Unknown key {part!r} in hotkey {text!r}")
    if vk is None:
        raise ValueError(f"Hotkey {text!r} has no non-modifier key")
    return mods, vk


def _user32():
    return ctypes.windll.user32


class _HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, owner: "GlobalHotkey"):
        super().__init__()
        self.owner = owner

    def nativeEventFilter(self, event_type, message):
        if event_type in (b"windows_generic_MSG", "windows_generic_MSG"):
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self.owner.hotkey_id:
                debug_print(f"Hotkey triggered: {self.owner.text}")
                self.owner.activated.emit()
                return True, 0
        return False, 0


class GlobalHotkey(QObject):
    """One registered system-wide hotkey; emits `activated` when pressed"""

    activated = pyqtSignal()

    def __init__(self, text: str, hotkey_id: int = 1, parent=None):
        super().__init__(parent)
        self.text = text
        self.hotkey_id = hotkey_id
        self.registered = False
        self._filter = None

    def register(self) -> bool:
        """
        Register with Windows. Returns False (and logs why) if the hotkey is
        malformed, not on Windows, or already taken by another application.
        """
        if self.registered:
            return True
        if sys.platform != "win32":
            debug_print("Global hotkey is only supported on Windows")
            return False
        try:
            mods, vk = parse_hotkey(self.text)
        except ValueError as e:
            debug_print(f"Invalid hotkey: {e}")
            return False

        # hWnd=None: WM_HOTKEY goes to this (the GUI) thread's message queue
        if not _user32().RegisterHotKey(None, self.hotkey_id, mods | MOD_NOREPEAT, vk):
            debug_print(f"RegisterHotKey({self.text}) failed, error {ctypes.GetLastError()} "
                        "(1409 = already registered by another application)")
            return False

        self._filter = _HotkeyFilter(self)
        QCoreApplication.instance().installNativeEventFilter(self._filter)
        self.registered = True
        debug_print(f"✓ Global hotkey registered: {self.text}")
        return True

    def unregister(self):
        if not self.registered:
            return
        _user32().UnregisterHotKey(None, self.hotkey_id)
        QCoreApplication.instance().removeNativeEventFilter(self._filter)
        self._filter = None
        self.registered = False
        debug_print(f"✓ Global hotkey unregistered: {self.text}")
