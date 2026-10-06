"""
Unit tests for the capture -> OCR -> clipboard flow in ScreenOCRApp.

Tray, screens, OCR engine and clipboard are all mocked.
"""

import pytest
from unittest.mock import MagicMock, patch

from PyQt5.QtCore import QRect
from PyQt5.QtGui import QPixmap, QColor
from PyQt5.QtWidgets import QSystemTrayIcon

import mocr.app


class FakeScreen:
    """QScreen stand-in that records grabWindow calls"""

    def __init__(self, x, y, width, height):
        self._geometry = QRect(x, y, width, height)
        self.grabs = []

    def geometry(self):
        return self._geometry

    def grabWindow(self, window_id, x=0, y=0, width=-1, height=-1):
        self.grabs.append((x, y, width, height))
        w = width if width > 0 else self._geometry.width()
        h = height if height > 0 else self._geometry.height()
        pixmap = QPixmap(w, h)
        pixmap.fill(QColor("white"))
        return pixmap


@pytest.fixture
def screens_with_gap(monkeypatch):
    screens = [FakeScreen(0, 0, 1920, 1080), FakeScreen(3840, 0, 1920, 1080)]
    monkeypatch.setattr(mocr.app.QApplication, "screens", staticmethod(lambda: screens))
    return screens


@pytest.fixture
def white_pixmap(qapp):
    pixmap = QPixmap(50, 20)
    pixmap.fill(QColor("white"))
    return pixmap


@pytest.fixture
def copy_text(monkeypatch):
    mock = MagicMock(return_value=True)
    monkeypatch.setattr(mocr.app.ClipboardManager, "copy_text", mock)
    return mock


@pytest.fixture
def in_tmp_cwd(tmp_path, monkeypatch):
    """last_capture.png is written to the cwd; keep it out of the repo"""
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestCaptureScreenRegion:
    """The real _capture_screen_region against fake screens"""

    def test_primary_screen(self, ocr_app, screens_with_gap):
        ocr_app._capture_screen_region(QRect(500, 500, 200, 100))
        assert screens_with_gap[0].grabs == [(500, 500, 200, 100)]
        assert screens_with_gap[1].grabs == []

    def test_secondary_screen_uses_screen_relative_offsets(self, ocr_app, screens_with_gap):
        ocr_app._capture_screen_region(QRect(4500, 300, 100, 50))
        assert screens_with_gap[1].grabs == [(660, 300, 100, 50)]
        assert screens_with_gap[0].grabs == []

    def test_selection_in_gap_uses_closest_screen(self, ocr_app, screens_with_gap):
        ocr_app._capture_screen_region(QRect(2000, 500, 200, 200))
        assert len(screens_with_gap[0].grabs) == 1
        assert screens_with_gap[1].grabs == []

    def test_spanning_selection_uses_largest_overlap(self, ocr_app, monkeypatch):
        screens = [FakeScreen(0, 0, 1920, 1080), FakeScreen(1920, 0, 1920, 1080)]
        monkeypatch.setattr(mocr.app.QApplication, "screens", staticmethod(lambda: screens))
        # 20px on screen 0, 180px on screen 1
        ocr_app._capture_screen_region(QRect(1900, 0, 200, 100))
        assert screens[0].grabs == []
        assert screens[1].grabs == [(-20, 0, 200, 100)]


class TestStartCapture:

    def test_grabs_all_screens_and_starts_overlay(self, ocr_app, screens_with_gap, monkeypatch):
        overlay = MagicMock()
        monkeypatch.setattr(mocr.app, "SelectionOverlay", MagicMock(return_value=overlay))

        ocr_app.start_capture()

        assert len(ocr_app.screens_data) == 2
        assert ocr_app.screens_data[1]["geometry"] == QRect(3840, 0, 1920, 1080)
        overlay.start_selection.assert_called_once()

    def test_reuses_overlay(self, ocr_app, screens_with_gap, monkeypatch):
        overlay_cls = MagicMock()
        monkeypatch.setattr(mocr.app, "SelectionOverlay", overlay_cls)

        ocr_app.start_capture()
        ocr_app.start_capture()

        overlay_cls.assert_called_once()
        assert overlay_cls.return_value.start_selection.call_count == 2


class TestSelectionMade:

    def test_ocr_text_copied_and_saved(self, ocr_app, mock_tray, white_pixmap, copy_text, in_tmp_cwd):
        ocr_app._capture_screen_region = MagicMock(return_value=white_pixmap)
        ocr_app.ocr_engine = MagicMock()
        ocr_app.ocr_engine.process_image.return_value = "hello world"

        ocr_app._on_selection_made(QRect(0, 0, 50, 20))

        ocr_app.ocr_engine.process_image.assert_called_once_with(white_pixmap, "eng")
        copy_text.assert_called_once_with("hello world")
        assert ocr_app.last_result == "hello world"
        assert (in_tmp_cwd / "last_capture.png").exists()

    def test_notification_only_when_enabled(self, ocr_app, mock_tray, white_pixmap, copy_text, in_tmp_cwd):
        ocr_app._capture_screen_region = MagicMock(return_value=white_pixmap)
        ocr_app.ocr_engine = MagicMock()
        ocr_app.ocr_engine.process_image.return_value = "abc"
        mock_tray.showMessage.reset_mock()

        ocr_app._on_selection_made(QRect(0, 0, 50, 20))
        mock_tray.showMessage.assert_not_called()

        ocr_app.settings["show_notifications"] = True
        ocr_app._on_selection_made(QRect(0, 0, 50, 20))
        assert mock_tray.showMessage.call_args.args[:2] == ("Text Copied", "Copied 3 characters to clipboard.")

    def test_ocr_error_is_reported_not_copied(self, ocr_app, mock_tray, white_pixmap, copy_text, in_tmp_cwd):
        ocr_app._capture_screen_region = MagicMock(return_value=white_pixmap)
        ocr_app.ocr_engine = MagicMock()
        ocr_app.ocr_engine.process_image.return_value = "ERROR: boom"
        mock_tray.showMessage.reset_mock()

        ocr_app._on_selection_made(QRect(0, 0, 50, 20))

        copy_text.assert_not_called()
        assert mock_tray.showMessage.call_args.args[0] == "OCR Error"

    def test_null_capture_is_reported(self, ocr_app, mock_tray, copy_text, in_tmp_cwd):
        ocr_app._capture_screen_region = MagicMock(return_value=QPixmap())
        ocr_app.ocr_engine = MagicMock()
        mock_tray.showMessage.reset_mock()

        ocr_app._on_selection_made(QRect(0, 0, 50, 20))

        ocr_app.ocr_engine.process_image.assert_not_called()
        assert mock_tray.showMessage.call_args.args[0] == "Capture Error"

    def test_auto_copy_disabled(self, ocr_app, white_pixmap, copy_text, in_tmp_cwd):
        ocr_app._capture_screen_region = MagicMock(return_value=white_pixmap)
        ocr_app.ocr_engine = MagicMock()
        ocr_app.ocr_engine.process_image.return_value = "text"
        ocr_app.settings["auto_copy"] = False

        ocr_app._on_selection_made(QRect(0, 0, 50, 20))

        copy_text.assert_not_called()
        assert ocr_app.last_result == "text"

    def test_result_dialog_when_enabled(self, ocr_app, white_pixmap, copy_text, in_tmp_cwd, monkeypatch):
        dialog_cls = MagicMock()
        monkeypatch.setattr(mocr.app, "ResultDialog", dialog_cls)
        ocr_app._capture_screen_region = MagicMock(return_value=white_pixmap)
        ocr_app.ocr_engine = MagicMock()
        ocr_app.ocr_engine.process_image.return_value = "text"
        ocr_app.settings["show_dialog"] = True

        ocr_app._on_selection_made(QRect(0, 0, 50, 20))

        dialog_cls.assert_called_once_with("text")
        dialog_cls.return_value.exec_.assert_called_once()


class TestSettingsAndTray:

    def test_settings_changed_updates_language(self, ocr_app, monkeypatch):
        monkeypatch.setattr(mocr.app.Config, "LANGUAGE", "eng")
        ocr_app._on_settings_changed({"language": "deu", "auto_copy": False})
        assert ocr_app.settings["language"] == "deu"
        assert ocr_app.settings["auto_copy"] is False
        assert mocr.app.Config.LANGUAGE == "deu"

    @pytest.mark.parametrize("reason", [QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick])
    def test_tray_click_starts_capture(self, ocr_app, reason):
        # mocr.app.QSystemTrayIcon is mocked; use the real enum values
        ocr_app.start_capture = MagicMock()
        with patch.object(mocr.app, "QSystemTrayIcon", QSystemTrayIcon):
            ocr_app._on_tray_activated(reason)
        ocr_app.start_capture.assert_called_once()

    def test_cancel_notifies(self, ocr_app, mock_tray):
        mock_tray.showMessage.reset_mock()
        ocr_app._on_selection_cancelled()
        assert mock_tray.showMessage.call_args.args[0] == "Capture Cancelled"


class TestReocrLastCapture:

    def test_reocr_runs_strategy_on_saved_capture(self, ocr_app, mock_tray, copy_text, in_tmp_cwd, white_pixmap):
        white_pixmap.save(str(in_tmp_cwd / "last_capture.png"), "PNG")
        ocr_app.ocr_engine = MagicMock()
        ocr_app.ocr_engine.process_file.return_value = "better text"
        mock_tray.showMessage.reset_mock()

        ocr_app.reocr_last_capture("upscale_2x")

        ocr_app.ocr_engine.process_file.assert_called_once_with(
            str(in_tmp_cwd / "last_capture.png"), "eng", "upscale_2x")
        copy_text.assert_called_once_with("better text")
        assert ocr_app.last_result == "better text"
        # Preview is shown even with notifications off
        assert mock_tray.showMessage.call_args.args[:2] == ("Re-OCR: upscale_2x", "better text")

    def test_reocr_without_capture(self, ocr_app, mock_tray, copy_text, in_tmp_cwd):
        ocr_app.ocr_engine = MagicMock()
        mock_tray.showMessage.reset_mock()

        ocr_app.reocr_last_capture("raw")

        ocr_app.ocr_engine.process_file.assert_not_called()
        assert mock_tray.showMessage.call_args.args[0] == "No Capture"

    def test_reocr_error_is_reported(self, ocr_app, mock_tray, copy_text, in_tmp_cwd, white_pixmap):
        white_pixmap.save(str(in_tmp_cwd / "last_capture.png"), "PNG")
        ocr_app.ocr_engine = MagicMock()
        ocr_app.ocr_engine.process_file.return_value = "ERROR: boom"
        mock_tray.showMessage.reset_mock()

        ocr_app.reocr_last_capture("raw")

        copy_text.assert_not_called()
        assert mock_tray.showMessage.call_args.args[0] == "OCR Error"

    def test_long_preview_is_truncated(self, ocr_app, mock_tray, copy_text, in_tmp_cwd, white_pixmap):
        white_pixmap.save(str(in_tmp_cwd / "last_capture.png"), "PNG")
        ocr_app.ocr_engine = MagicMock()
        ocr_app.ocr_engine.process_file.return_value = "x" * 500

        ocr_app.reocr_last_capture("raw")

        preview = mock_tray.showMessage.call_args.args[1]
        assert len(preview) == 201 and preview.endswith("…")
