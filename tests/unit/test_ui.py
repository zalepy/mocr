"""
Unit tests for the selection overlay and dialogs. Nothing is shown on screen:
event handlers are called directly and painting goes to an offscreen pixmap.
"""

import pytest
from unittest.mock import MagicMock

from PyQt5.QtCore import Qt, QPoint, QRect, QEvent
from PyQt5.QtGui import QMouseEvent, QKeyEvent, QPixmap

import mocr.ui
from mocr.ui import SelectionOverlay, ResultDialog, SettingsDialog


def mouse(event_type, x, y, button=Qt.LeftButton):
    return QMouseEvent(event_type, QPoint(x, y), button, button, Qt.NoModifier)


@pytest.fixture
def overlay(qapp):
    widget = SelectionOverlay([])
    widget.made = []
    widget.cancelled = []
    widget.selection_made.connect(widget.made.append)
    widget.selection_cancelled.connect(lambda: widget.cancelled.append(True))
    # hide() is harmless, but keep it from touching window state
    widget.hide = MagicMock()
    return widget


def drag(overlay, start, end):
    overlay.mousePressEvent(mouse(QEvent.MouseButtonPress, *start))
    overlay.mouseMoveEvent(mouse(QEvent.MouseMove, *end, button=Qt.NoButton))
    overlay.mouseReleaseEvent(mouse(QEvent.MouseButtonRelease, *end))


class TestSelectionOverlay:

    def test_drag_emits_normalized_rect(self, overlay):
        # Drag from bottom-right to top-left
        drag(overlay, (300, 200), (100, 50))

        assert overlay.made == [QRect(QPoint(100, 50), QPoint(300, 200))]
        overlay.hide.assert_called_once()

    def test_emits_global_coordinates(self, overlay):
        # Two 4K monitors at 200%: local x >= 1920 is the second monitor, whose
        # geometry starts at x=3840. mapToGlobal does the per-screen conversion.
        def map_to_global(p):
            return QPoint(p.x() + 1920 if p.x() >= 1920 else p.x(), p.y())
        overlay.mapToGlobal = map_to_global

        drag(overlay, (2000, 100), (2200, 200))

        assert overlay.made == [QRect(QPoint(3920, 100), QPoint(4120, 200))]

    def test_tiny_selection_is_ignored(self, overlay):
        drag(overlay, (100, 100), (104, 104))

        assert overlay.made == []
        assert overlay.selection_rect.isNull()

    def test_escape_cancels(self, overlay):
        overlay.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))

        assert overlay.cancelled == [True]
        assert not overlay.selecting

    def test_right_click_does_not_start_selection(self, overlay):
        overlay.mousePressEvent(mouse(QEvent.MouseButtonPress, 10, 10, button=Qt.RightButton))
        assert not overlay.selecting

    @pytest.mark.parametrize("selecting", [False, True])
    def test_paint_renders_offscreen(self, overlay, selecting):
        overlay.resize(400, 300)
        overlay.selecting = selecting
        overlay.selection_rect = QRect(50, 60, 100, 80)
        target = QPixmap(400, 300)
        overlay.render(target)  # runs paintEvent without showing the widget
        assert not target.isNull()


class TestResultDialog:

    def test_copy_uses_edited_text(self, qapp, monkeypatch):
        copy_text = MagicMock(return_value=True)
        monkeypatch.setattr(mocr.ui.ClipboardManager, "copy_text", copy_text)
        dialog = ResultDialog("original")
        dialog.text_edit.setPlainText("edited")

        dialog._on_copy()

        copy_text.assert_called_once_with("edited")


class TestSettingsDialog:

    def test_save_emits_settings(self, qapp):
        dialog = SettingsDialog({"language": "eng", "auto_copy": True,
                                 "show_dialog": False, "show_notifications": False})
        emitted = []
        dialog.settings_changed.connect(emitted.append)

        dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("deu"))
        dialog.auto_copy_check.setChecked(False)
        dialog.show_notifications_check.setChecked(True)
        dialog._on_save()

        assert emitted == [{"language": "deu", "auto_copy": False,
                            "show_dialog": False, "show_notifications": True}]

    def test_preselects_current_language(self, qapp):
        dialog = SettingsDialog({"language": "jpn"})
        assert dialog.language_combo.currentData() == "jpn"
