from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QClipboard

try:
    import win32clipboard
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

class ClipboardManager:
    """Manages clipboard operations with enhanced Windows support"""
    
    @staticmethod
    def copy_text(text: str) -> bool:
        """
        Copy text to clipboard.
        
        Args:
            text: Text to copy
        
        Returns:
            True if successful, False otherwise
        """
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(text, QClipboard.Clipboard)
            
            # Also set in selection clipboard (middle mouse button paste on Linux)
            clipboard.setText(text, QClipboard.Selection)
            
            # On Windows, try to use win32clipboard for better compatibility
            if WIN32_AVAILABLE:
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass  # Fall back to Qt clipboard which already worked
            
            return True
        except Exception as e:
            print(f"Failed to copy to clipboard: {e}")
            return False
    
    @staticmethod
    def get_text() -> str:
        """Get current clipboard text"""
        clipboard = QApplication.clipboard()
        return clipboard.text()
