#!/usr/bin/env python3
"""
Screen Capture OCR Tool
A Windows-like screen capture tool that performs OCR on the selected region
and copies the text to clipboard instead of the image.

Usage:
    python screen_ocr.py

Hotkey: Ctrl+Alt+Print Screen (configurable) to start screen capture
Press ESC to cancel selection
"""

import sys
import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple
import threading

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QSystemTrayIcon, QMenu, QAction,
    QDialog, QSpinBox, QComboBox, QGroupBox, QFormLayout, QMessageBox,
    QCheckBox
)
from PyQt5.QtCore import (
    Qt, QRect, QPoint, QSize, QTimer, pyqtSignal, QObject, QBuffer
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QScreen, QGuiApplication,
    QIcon, QPixmap, QCursor, QGuiApplication, QClipboard
)

# OCR imports - will gracefully handle if not installed
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# Keyboard hotkey support
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

# Windows-specific clipboard enhancements
try:
    import win32clipboard
    import win32con
    import win32api
    import win32registry
    import win32gui
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


class WindowsIntegration:
    """Windows-specific integration utilities"""
    
    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows"""
        return sys.platform == 'win32'
    
    @staticmethod
    def get_startup_folder() -> Path:
        """Get Windows startup folder path"""
        if WindowsIntegration.is_windows():
            return Path(os.environ['APPDATA']) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup'
        return Path.home()
    
    @staticmethod
    def add_to_startup(script_path: str, name: str = "ScreenOCR"):
        """Add script to Windows startup"""
        if not WindowsIntegration.is_windows():
            return False
        
        startup_folder = WindowsIntegration.get_startup_folder()
        shortcut_path = startup_folder / f"{name}.bat"
        
        # Create a batch file that runs the Python script
        with open(shortcut_path, 'w') as f:
            f.write(f'@echo off\npythonw "{script_path}"\n')
        
        return True
    
    @staticmethod
    def remove_from_startup(name: str = "ScreenOCR"):
        """Remove script from Windows startup"""
        startup_folder = WindowsIntegration.get_startup_folder()
        shortcut_path = startup_folder / f"{name}.bat"
        
        if shortcut_path.exists():
            shortcut_path.unlink()
            return True
        return False
    
    @staticmethod
    def set_autostart_registry(enabled: bool, script_path: str, name: str = "ScreenOCR"):
        """Set autostart via Windows registry"""
        if not WIN32_AVAILABLE:
            return False
        
        try:
            key = win32registry.OpenKey(
                win32registry.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                win32registry.KEY_SET_VALUE
            )
            
            if enabled:
                win32registry.SetValueEx(key, name, 0, win32registry.REG_SZ, f'pythonw "{script_path}"')
            else:
                try:
                    win32registry.DeleteValue(key, name)
                except Exception:
                    pass
            
            win32registry.CloseKey(key)
            return True
        except Exception as e:
            print(f"Registry error: {e}")
            return False
    
    @staticmethod
    def show_native_notification(title: str, message: str, icon_type: str = "info"):
        """Show a native Windows notification"""
        if not WIN32_AVAILABLE:
            return False
        
        try:
            # Use PowerShell for toast notifications
            icon_map = {
                "info": "Information",
                "warning": "Warning", 
                "error": "Error"
            }
            
            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            
            $template = @"
            <toast>
                <visual>
                    <binding template="ToastText02">
                        <text id="1">{title}</text>
                        <text id="2">{message}</text>
                    </binding>
                </visual>
            </toast>
"@
            
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $xml.LoadXml($template)
            $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Screen OCR").Show($toast)
            '''
            
            subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True
        except Exception as e:
            print(f"Notification error: {e}")
            return False


class Config:
    """Application configuration"""
    # Hotkey for triggering screen capture
    HOTKEY = "ctrl+alt+prtscn"
    
    # OCR Settings
    TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Default Windows path
    LANGUAGE = "eng"  # OCR language
    
    # Selection overlay settings
    SELECTION_COLOR = QColor(0, 120, 215, 200)  # Windows blue
    SELECTION_BORDER_WIDTH = 2
    OVERLAY_OPACITY = 0.3
    
    # Supported OCR languages
    SUPPORTED_LANGUAGES = {
        "English": "eng",
        "Chinese (Simplified)": "chi_sim",
        "Chinese (Traditional)": "chi_tra",
        "Japanese": "jpn",
        "Korean": "kor",
        "German": "deu",
        "French": "fra",
        "Spanish": "spa",
        "Russian": "rus",
        "Arabic": "ara",
    }


class SelectionOverlay(QWidget):
    """
    Fullscreen transparent overlay widget for rectangular selection.
    Mimics Windows Snipping Tool / Win+Shift+S behavior.
    """
    
    selection_made = pyqtSignal(QRect)  # Signal emitted when selection is complete
    selection_cancelled = pyqtSignal()   # Signal emitted when selection is cancelled
    
    def __init__(self, screens_data: list):
        super().__init__()
        self.screens_data = screens_data
        
        # Selection state
        self.selecting = False
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.selection_rect = QRect()
        
        # Setup window properties for fullscreen overlay
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        
        # Get combined screen geometry (for multi-monitor support)
        self.total_geometry = self._get_combined_screen_geometry()
        self.setGeometry(self.total_geometry)
        
        # Cursor
        self.setCursor(Qt.CrossCursor)
        
        # Instructions
        self.instruction_text = "Click and drag to select an area. Press ESC to cancel."
        
    def _get_combined_screen_geometry(self) -> QRect:
        """Get combined geometry of all screens for multi-monitor support"""
        screens = QGuiApplication.screens()
        if not screens:
            return QRect(0, 0, 1920, 1080)
        
        combined = screens[0].geometry()
        for screen in screens[1:]:
            combined = combined.united(screen.geometry())
        return combined
    
    def start_selection(self):
        """Start the selection process"""
        self.show()
        self.activateWindow()
        self.raise_()
        self.setFocus()
        self.selecting = False
        self.selection_rect = QRect()
        self.update()
    
    def paintEvent(self, event):
        """Paint the overlay with darkening effect and selection rectangle"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw semi-transparent overlay on entire screen
        overlay_color = QColor(0, 0, 0, int(255 * Config.OVERLAY_OPACITY))
        painter.fillRect(self.rect(), overlay_color)
        
        # Draw selection rectangle
        if not self.selection_rect.isNull():
            # Clear the overlay in the selection area (show original screen)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(self.selection_rect, Qt.transparent)
            
            # Draw selection border
            pen = QPen(Config.SELECTION_COLOR)
            pen.setWidth(Config.SELECTION_BORDER_WIDTH)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.selection_rect)
            
            # Draw corner handles for visual feedback
            handle_size = 8
            painter.setBrush(QBrush(Config.SELECTION_COLOR))
            corners = [
                self.selection_rect.topLeft(),
                self.selection_rect.topRight(),
                self.selection_rect.bottomLeft(),
                self.selection_rect.bottomRight()
            ]
            for corner in corners:
                painter.drawRect(corner.x() - handle_size//2, corner.y() - handle_size//2, 
                               handle_size, handle_size)
            
            # Draw size indicator
            size_text = f"{abs(self.selection_rect.width())} x {abs(self.selection_rect.height())}"
            font = QFont("Segoe UI", 10)
            painter.setFont(font)
            painter.setPen(Qt.white)
            
            # Position text above selection
            text_pos = self.selection_rect.topLeft() - QPoint(0, 25)
            if text_pos.y() < 30:
                text_pos = self.selection_rect.bottomLeft() + QPoint(0, 20)
            
            # Draw text background
            from PyQt5.QtGui import QFontMetrics
            fm = QFontMetrics(font)
            text_rect = fm.boundingRect(size_text)
            text_rect.moveTopLeft(text_pos)
            text_rect.adjust(-5, -2, 5, 2)
            painter.fillRect(text_rect, QColor(0, 0, 0, 180))
            painter.drawText(text_pos, size_text)
        
        # Draw instructions at top
        if not self.selecting:
            font = QFont("Segoe UI", 12)
            painter.setFont(font)
            painter.setPen(Qt.white)
            
            # Draw instruction background
            from PyQt5.QtGui import QFontMetrics
            fm = QFontMetrics(font)
            inst_rect = fm.boundingRect(self.instruction_text)
            inst_rect.moveCenter(QPoint(self.width() // 2, 50))
            inst_rect.adjust(-20, -10, 20, 10)
            
            painter.fillRect(inst_rect, QColor(0, 0, 0, 200))
            painter.drawText(inst_rect, Qt.AlignCenter, self.instruction_text)
    
    def mousePressEvent(self, event):
        """Handle mouse press to start selection"""
        if event.button() == Qt.LeftButton:
            self.selecting = True
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.selection_rect = QRect(self.start_point, self.end_point)
            self.update()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move to update selection rectangle"""
        if self.selecting:
            self.end_point = event.pos()
            self.selection_rect = QRect(self.start_point, self.end_point).normalized()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to complete selection"""
        if event.button() == Qt.LeftButton and self.selecting:
            self.selecting = False
            if not self.selection_rect.isNull() and self.selection_rect.width() > 5 and self.selection_rect.height() > 5:
                self.hide()
                self.selection_made.emit(self.selection_rect)
            else:
                self.selection_rect = QRect()
                self.update()
    
    def keyPressEvent(self, event):
        """Handle ESC key to cancel selection"""
        if event.key() == Qt.Key_Escape:
            self.hide()
            self.selection_rect = QRect()
            self.selecting = False
            self.selection_cancelled.emit()
        else:
            super().keyPressEvent(event)


class OCREngine:
    """OCR processing engine using Tesseract"""
    
    def __init__(self):
        self._setup_tesseract()
    
    def _setup_tesseract(self):
        """Setup Tesseract OCR path if on Windows"""
        if not TESSERACT_AVAILABLE:
            return
        
        # Try common Tesseract installation paths
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Tesseract-OCR\tesseract.exe",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break
    
    def process_image(self, image: QPixmap, language: str = None) -> str:
        """
        Process a QPixmap image and return extracted text.
        
        Args:
            image: QPixmap containing the captured screen region
            language: OCR language code (e.g., 'eng', 'chi_sim')
        
        Returns:
            Extracted text string
        """
        if not TESSERACT_AVAILABLE:
            return "ERROR: pytesseract not installed. Install with: pip install pytesseract\nAlso install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki"
        
        if language is None:
            language = Config.LANGUAGE
        
        try:
            # Convert QPixmap to PIL Image
            import io
            
            # Save QPixmap to bytes buffer
            buffer = QBuffer()
            buffer.open(QBuffer.ReadWrite)
            image.save(buffer, "PNG")
            
            # Get bytes from buffer and convert to PIL Image
            buffer_bytes = buffer.data()
            bytes_buffer = io.BytesIO(buffer_bytes)
            pil_image = Image.open(bytes_buffer)
            
            # Perform OCR
            text = pytesseract.image_to_string(pil_image, lang=language)
            
            # Clean up the text
            text = text.strip()
            
            if not text:
                return "(No text detected in the selected region)"
            
            return text
            
        except pytesseract.TesseractNotFoundError:
            return "ERROR: Tesseract OCR not found.\nPlease install from: https://github.com/UB-Mannheim/tesseract/wiki\nAnd ensure the path is correct in Config.TESSERACT_PATH"
        except Exception as e:
            return f"ERROR: OCR processing failed: {str(e)}"


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


class ResultDialog(QDialog):
    """Dialog to display OCR results and allow editing before copying"""
    
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OCR Result")
        self.setMinimumSize(500, 400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        layout = QVBoxLayout(self)
        
        # Instructions
        info_label = QLabel("Text extracted from screen capture. Edit if needed, then click Copy to Clipboard.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Text edit
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.text_edit)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self._on_copy)
        copy_btn.setDefault(True)
        button_layout.addWidget(copy_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _on_copy(self):
        """Copy text and close dialog"""
        text = self.text_edit.toPlainText()
        if ClipboardManager.copy_text(text):
            self.accept()


class SettingsDialog(QDialog):
    """Settings dialog for configuring the OCR tool"""
    
    settings_changed = pyqtSignal(dict)
    
    def __init__(self, current_settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        
        self.settings = current_settings.copy()
        
        layout = QVBoxLayout(self)
        
        # Hotkey settings
        hotkey_group = QGroupBox("Hotkey")
        hotkey_layout = QFormLayout(hotkey_group)
        
        self.hotkey_edit = QLabel(current_settings.get('hotkey', Config.HOTKEY))
        hotkey_layout.addRow("Capture Hotkey:", self.hotkey_edit)
        
        hotkey_info = QLabel("To change hotkey, edit the Config class in screen_ocr.py")
        hotkey_info.setStyleSheet("color: gray; font-style: italic;")
        hotkey_layout.addRow("", hotkey_info)
        
        layout.addWidget(hotkey_group)
        
        # OCR Settings
        ocr_group = QGroupBox("OCR Settings")
        ocr_layout = QFormLayout(ocr_group)
        
        self.language_combo = QComboBox()
        for name, code in Config.SUPPORTED_LANGUAGES.items():
            self.language_combo.addItem(name, code)
        
        # Set current language
        current_lang = current_settings.get('language', Config.LANGUAGE)
        index = self.language_combo.findData(current_lang)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        
        ocr_layout.addRow("OCR Language:", self.language_combo)
        
        # Tesseract path info
        if TESSERACT_AVAILABLE:
            tess_status = "Available"
            tess_style = "color: green;"
        else:
            tess_status = "Not Found - Install pytesseract and Tesseract OCR"
            tess_style = "color: red;"
        
        tess_label = QLabel(tess_status)
        tess_label.setStyleSheet(tess_style)
        ocr_layout.addRow("Tesseract:", tess_label)
        
        layout.addWidget(ocr_group)
        
        # Auto-copy setting
        self.auto_copy_check = QCheckBox("Automatically copy text to clipboard after capture")
        self.auto_copy_check.setChecked(current_settings.get('auto_copy', True))
        layout.addWidget(self.auto_copy_check)
        
        # Show result dialog setting
        self.show_dialog_check = QCheckBox("Show result dialog after capture")
        self.show_dialog_check.setChecked(current_settings.get('show_dialog', False))
        layout.addWidget(self.show_dialog_check)
        
        # Notifications setting
        self.show_notifications_check = QCheckBox("Show notifications when text is copied")
        self.show_notifications_check.setChecked(current_settings.get('show_notifications', False))
        layout.addWidget(self.show_notifications_check)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _on_save(self):
        """Save settings and emit signal"""
        self.settings['language'] = self.language_combo.currentData()
        self.settings['auto_copy'] = self.auto_copy_check.isChecked()
        self.settings['show_dialog'] = self.show_dialog_check.isChecked()
        self.settings['show_notifications'] = self.show_notifications_check.isChecked()
        self.settings_changed.emit(self.settings)
        self.accept()
    
    def get_settings(self) -> dict:
        return self.settings


class ScreenOCRApp(QObject):
    """Main application controller"""
    
    def __init__(self):
        super().__init__()
        
        # Store captured screenshots
        self.screens_data = []
        
        # Settings
        self.settings = {
            'hotkey': Config.HOTKEY,
            'language': Config.LANGUAGE,
            'auto_copy': True,
            'show_dialog': False,
            'show_notifications': False
        }
        
        # OCR Engine
        self.ocr_engine = OCREngine()
        
        # Selection overlay (will be created when needed)
        self.overlay: Optional[SelectionOverlay] = None
        
        # Control window (backup UI if tray doesn't work)
        self.control_window: Optional[QMainWindow] = None
        
        # Hotkey polling state
        self.hotkey_timer: Optional[QTimer] = None
        self.hotkey_pressed = False
        self.hotkey_key_sequence: list = []  # For tracking multi-key combinations
        
        # Create system tray
        self._create_system_tray()
        
        # Setup hotkey
        self._setup_hotkey()
    
    def _create_control_window(self):
        """Create a backup control window if tray icon doesn't respond"""
        if self.control_window is None:
            self.control_window = QMainWindow()
            self.control_window.setWindowTitle("Screen OCR - Control Panel")
            self.control_window.setWindowIcon(self.tray_icon.icon())
            self.control_window.setGeometry(100, 100, 300, 200)
            
            central_widget = QWidget()
            layout = QVBoxLayout(central_widget)
            
            title = QLabel("Screen OCR Tool")
            title.setStyleSheet("font-weight: bold; font-size: 14px;")
            layout.addWidget(title)
            
            info = QLabel("Use the buttons below or right-click the tray icon")
            info.setWordWrap(True)
            layout.addWidget(info)
            
            layout.addSpacing(10)
            
            capture_btn = QPushButton("📸 Capture Screen")
            capture_btn.clicked.connect(self.start_capture)
            layout.addWidget(capture_btn)
            
            settings_btn = QPushButton("⚙️ Settings")
            settings_btn.clicked.connect(self.show_settings)
            layout.addWidget(settings_btn)
            
            result_btn = QPushButton("📄 Show Last Result")
            result_btn.clicked.connect(self.show_last_result)
            layout.addWidget(result_btn)
            
            layout.addSpacing(10)
            
            exit_btn = QPushButton("❌ Exit")
            exit_btn.clicked.connect(self.quit_app)
            exit_btn.setStyleSheet("background-color: #f0f0f0;")
            layout.addWidget(exit_btn)
            
            layout.addStretch()
            
            self.control_window.setCentralWidget(central_widget)
            self.control_window.setWindowFlags(self.control_window.windowFlags() | Qt.WindowStaysOnTopHint)
        
        return self.control_window
    
    def _create_system_tray(self):
        """Create system tray icon and menu"""
        self.tray_icon = QSystemTrayIcon()
        
        # Create icon (a simple colored square)
        icon_pixmap = QPixmap(64, 64)
        icon_pixmap.fill(Config.SELECTION_COLOR)
        self.tray_icon.setIcon(QIcon(icon_pixmap))
        
        # Create tray menu
        tray_menu = QMenu()
        
        # Capture action - primary action with icon
        capture_action = QAction("📸 Capture Screen", tray_menu)
        capture_action.setToolTip("Capture and OCR a screen region\n(Shortcut: Ctrl+Alt+Print Screen)")
        capture_action.triggered.connect(self.start_capture)
        tray_menu.addAction(capture_action)
        
        tray_menu.addSeparator()
        
        # Settings action
        settings_action = QAction("⚙️ Settings", tray_menu)
        settings_action.setToolTip("Configure OCR settings")
        settings_action.triggered.connect(self.show_settings)
        tray_menu.addAction(settings_action)
        
        # Show last result action
        show_last_action = QAction("📄 Show Last Result", tray_menu)
        show_last_action.setToolTip("Display the most recent OCR result")
        show_last_action.triggered.connect(self.show_last_result)
        tray_menu.addAction(show_last_action)
        
        tray_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("❌ Exit", tray_menu)
        exit_action.setToolTip("Quit the Screen OCR application")
        exit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        
        # Show tray icon
        self.tray_icon.show()
        
        # Show welcome message
        self.tray_icon.showMessage(
            "Screen OCR Tool Started",
            "Right-click tray icon for menu.\nPress Ctrl+Alt+Print Screen to capture or click 'Exit' to quit.",
            QSystemTrayIcon.Information,
            5000
        )
        
        # Store last OCR result
        self.last_result = ""
    
    def _on_tray_activated(self, reason):
        """Handle tray icon activation"""
        reasons = {
            QSystemTrayIcon.Unknown: "Unknown",
            QSystemTrayIcon.Context: "Context (Right-click)",
            QSystemTrayIcon.DoubleClick: "Double-click",
            QSystemTrayIcon.Trigger: "Left-click",
            QSystemTrayIcon.MiddleClick: "Middle-click",
        }
        
        reason_name = reasons.get(reason, str(reason))
        print(f"Tray activated: {reason_name}")
        
        if reason == QSystemTrayIcon.DoubleClick or reason == QSystemTrayIcon.Trigger:
            # Left-click or double-click - start capture
            print("  → Capturing screen")
            self.start_capture()
        elif reason == QSystemTrayIcon.Context:
            # Right-click - show menu at cursor position
            print("  → Showing context menu")
            menu = self.tray_icon.contextMenu()
            if menu:
                menu.popup(QCursor.pos())
        else:
            # Unknown activation - show control panel as fallback
            print("  → Showing control panel (fallback)")
            window = self._create_control_window()
            window.show()
            window.raise_()
            window.activateWindow()
    
    def _setup_hotkey(self):
        """Setup global hotkey for screen capture using Qt timer polling"""
        if not KEYBOARD_AVAILABLE:
            print("keyboard module not available. Hotkey will not work.")
            print("Install with: pip install keyboard")
            self.tray_icon.showMessage(
                "Hotkey Unavailable",
                "keyboard module not installed. Use tray menu to capture.\nInstall with: pip install keyboard",
                QSystemTrayIcon.Warning,
                5000
            )
            return
        
        # Parse the hotkey string into key names
        # Format: "ctrl+alt+prtscn" -> ["ctrl", "alt", "prtscn"]
        self.hotkey_keys = Config.HOTKEY.lower().split("+")
        
        # Create and start a timer to poll for hotkey
        self.hotkey_timer = QTimer()
        self.hotkey_timer.timeout.connect(self._check_hotkey_pressed)
        # Check every 100ms
        self.hotkey_timer.start(100)
        
        print(f"✓ Hotkey polling started for: {Config.HOTKEY}")
        print("  (Using Qt-based timer, will not block UI)")
    
    def _check_hotkey_pressed(self):
        """Check if hotkey is pressed (called by Qt timer)"""
        try:
            # Check if all keys in the hotkey combination are pressed
            all_pressed = all(keyboard.is_pressed(key) for key in self.hotkey_keys)
            
            if all_pressed and not self.hotkey_pressed:
                # Hotkey was just pressed
                self.hotkey_pressed = True
                print(f"Hotkey triggered: {Config.HOTKEY}")
                # Call start_capture in the Qt main thread (it's already running in main thread)
                self.start_capture()
            elif not all_pressed and self.hotkey_pressed:
                # Hotkey was released
                self.hotkey_pressed = False
                
        except Exception as e:
            # Silently ignore errors (e.g., invalid key names)
            pass
    
    def _stop_hotkey_polling(self):
        """Stop the hotkey polling timer"""
        if self.hotkey_timer is not None:
            self.hotkey_timer.stop()
            self.hotkey_timer.deleteLater()
            self.hotkey_timer = None
            print("✓ Hotkey polling stopped")

    def _capture_screen_region(self, rect: QRect) -> QPixmap:
        """Capture a specific region of the screen"""
        screen = QGuiApplication.primaryScreen()
        
        # If rect spans multiple screens, we need to capture from the correct screen
        screens = QGuiApplication.screens()
        for s in screens:
            if s.geometry().intersects(rect):
                # Get the pixmap from this screen
                pixmap = s.grabWindow(0, 
                    rect.x() - s.geometry().x(),
                    rect.y() - s.geometry().y(),
                    rect.width(),
                    rect.height()
                )
                return pixmap
        
        # Fallback to primary screen
        return screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
    
    def start_capture(self):
        """Start the screen capture process"""
        # Capture full screen before showing overlay
        self.screens_data = []
        screens = QGuiApplication.screens()
        for screen in screens:
            pixmap = screen.grabWindow(0)
            self.screens_data.append({
                'pixmap': pixmap,
                'geometry': screen.geometry()
            })
        
        # Create and show selection overlay
        if self.overlay is None:
            self.overlay = SelectionOverlay(self.screens_data)
            self.overlay.selection_made.connect(self._on_selection_made)
            self.overlay.selection_cancelled.connect(self._on_selection_cancelled)
        
        self.overlay.screens_data = self.screens_data
        self.overlay.start_selection()
    
    def _on_selection_made(self, rect: QRect):
        """Handle selection completion"""
        # Capture the selected region
        captured_pixmap = self._capture_screen_region(rect)
        
        if captured_pixmap.isNull():
            self.tray_icon.showMessage(
                "Capture Error",
                "Failed to capture screen region.",
                QSystemTrayIcon.Warning,
                3000
            )
            return
        
        # Perform OCR
        language = self.settings.get('language', Config.LANGUAGE)
        ocr_text = self.ocr_engine.process_image(captured_pixmap, language)
        
        # Store result
        self.last_result = ocr_text
        
        # Check for errors
        if ocr_text.startswith("ERROR"):
            self.tray_icon.showMessage(
                "OCR Error",
                ocr_text,
                QSystemTrayIcon.Critical,
                5000
            )
            return
        
        # Handle result
        if self.settings.get('auto_copy', True):
            ClipboardManager.copy_text(ocr_text)
            if self.settings.get('show_notifications', True):
                self.tray_icon.showMessage(
                    "Text Copied",
                    f"Copied {len(ocr_text)} characters to clipboard.",
                    QSystemTrayIcon.Information,
                    2000
                )
        
        if self.settings.get('show_dialog', False):
            dialog = ResultDialog(ocr_text)
            dialog.exec_()
    
    def _on_selection_cancelled(self):
        """Handle selection cancellation"""
        self.tray_icon.showMessage(
            "Capture Cancelled",
            "Screen capture was cancelled.",
            QSystemTrayIcon.Information,
            1500
        )
    
    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self.settings)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec_()
    
    def _on_settings_changed(self, new_settings: dict):
        """Handle settings changes"""
        self.settings.update(new_settings)
        Config.LANGUAGE = new_settings.get('language', Config.LANGUAGE)
    
    def show_last_result(self):
        """Show the last OCR result"""
        if self.last_result:
            dialog = ResultDialog(self.last_result)
            dialog.exec_()
        else:
            self.tray_icon.showMessage(
                "No Result",
                "No previous OCR result available.",
                QSystemTrayIcon.Information,
                2000
            )
    
    def quit_app(self):
        """Quit the application"""
        print("\nShutting down Screen OCR Tool...")
        
        # Close control window if open
        if self.control_window is not None:
            self.control_window.close()
        
        # Stop hotkey polling timer
        self._stop_hotkey_polling()
        
        self.tray_icon.hide()
        QApplication.quit()
        print("✓ Application closed")


def main():
    """Main entry point"""
    print("=" * 60)
    print("Screen OCR Tool v1.0.0")
    print("=" * 60)
    
    # Check if running as admin (needed for hotkey on Windows)
    if sys.platform == 'win32':
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                print("⚠️  WARNING: Not running as Administrator")
                print("    Hotkeys may not work properly.")
                print("    For full functionality, run as Administrator.")
        except Exception:
            pass
    
    # High DPI support
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    
    # Set application info
    app.setApplicationName("Screen OCR Tool")
    app.setApplicationVersion("1.0.0")
    
    # Create main app controller
    main_app = ScreenOCRApp()
    
    print("\n✓ Application started successfully")
    print("\nHow to use:")
    print("  1. Press Ctrl+Alt+Print Screen to trigger screen capture")
    print("  2. Look for blue square icon in system tray")
    print("  3. Right-click tray icon for menu (Capture, Settings, Exit)")
    print("  4. If tray doesn't respond, check console for debug info")
    print("\nPress Ctrl+C to exit immediately if needed.\n")
    
    # Run event loop
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
