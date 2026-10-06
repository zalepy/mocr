import sys

# Debug flag
DEBUG = "--debug" in sys.argv

# Keyboard availability check
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

def debug_print(*args, **kwargs):
    """Print only if debug mode is enabled"""
    if DEBUG:
        print(*args, **kwargs)

class WindowsIntegration:
    """Windows-specific integration utilities"""

    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows"""
        return sys.platform == 'win32'
