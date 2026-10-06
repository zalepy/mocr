"""
E2E tests for the clipboard manager against the real system clipboard
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from mocr.clipboard import ClipboardManager


@pytest.mark.usefixtures("preserve_clipboard")
class TestClipboardManager:
    """Test Clipboard Manager functionality"""

    def test_copy_text_returns_bool(self):
        """Test that copy_text returns a boolean"""
        result = ClipboardManager.copy_text("test text")
        assert isinstance(result, bool)

    def test_copy_simple_text(self):
        """Test copying simple text to clipboard"""
        test_text = "Hello, World!"
        result = ClipboardManager.copy_text(test_text)
        assert result is True

        # Verify by reading back
        retrieved = ClipboardManager.get_text()
        assert retrieved == test_text

    def test_copy_multiline_text(self):
        """Test copying multiline text"""
        test_text = "Line 1\nLine 2\nLine 3"
        result = ClipboardManager.copy_text(test_text)
        assert result is True

        retrieved = ClipboardManager.get_text()
        assert retrieved == test_text

    def test_copy_empty_string(self):
        """Test copying empty string"""
        result = ClipboardManager.copy_text("")
        assert result is True

        retrieved = ClipboardManager.get_text()
        assert retrieved == ""

    def test_copy_unicode_text(self):
        """Test copying unicode text"""
        test_text = "Hello 世界 مرحبا мир"
        result = ClipboardManager.copy_text(test_text)
        assert result is True

        retrieved = ClipboardManager.get_text()
        assert retrieved == test_text

    def test_get_text_returns_string(self):
        """Test that get_text returns a string"""
        result = ClipboardManager.get_text()
        assert isinstance(result, str)

    def test_copy_long_text(self):
        """Test copying very long text"""
        test_text = "A" * 10000
        result = ClipboardManager.copy_text(test_text)
        assert result is True

        retrieved = ClipboardManager.get_text()
        assert len(retrieved) == 10000
