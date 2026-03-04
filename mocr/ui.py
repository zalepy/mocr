from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QDialog, QSpinBox, QComboBox, QGroupBox, 
    QFormLayout, QMessageBox, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QPoint
from PyQt5.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont, QGuiApplication, 
    QCursor, QFontMetrics
)

from .config import Config
from .clipboard import ClipboardManager
from .utils import debug_print, WIN32_AVAILABLE
from .ocr import TESSERACT_AVAILABLE

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
        # Use simpler flags to ensure window spans all screens
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint
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
        
        debug_print(f"\\n=== Multi-Monitor Debug Info ===")
        debug_print(f"Number of screens: {len(screens)}")
        
        combined = screens[0].geometry()
        debug_print(f"Screen 0: x={combined.x()}, y={combined.y()}, w={combined.width()}, h={combined.height()}")
        
        for idx, screen in enumerate(screens[1:], start=1):
            geo = screen.geometry()
            debug_print(f"Screen {idx}: x={geo.x()}, y={geo.y()}, w={geo.width()}, h={geo.height()}")
            combined = combined.united(geo)
        
        debug_print(f"Combined: x={combined.x()}, y={combined.y()}, w={combined.width()}, h={combined.height()}")
        debug_print(f"================================\\n")
        return combined
    
    def start_selection(self):
        """Start the selection process"""
        # Recalculate geometry in case monitor setup changed
        self.total_geometry = self._get_combined_screen_geometry()
        self.setGeometry(self.total_geometry)
        
        debug_print(f"Overlay geometry set to: x={self.total_geometry.x()}, y={self.total_geometry.y()}, "
                    f"w={self.total_geometry.width()}, h={self.total_geometry.height()}")
        
        # Ensure window is positioned correctly and shown
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)  # Unminimize if minimized
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
        
        # Debug: Log actual widget geometry
        debug_print(f"[paintEvent] Widget size: {self.width()}x{self.height()}, "
                    f"Geometry: x={self.x()}, y={self.y()}, w={self.width()}, h={self.height()}")
        
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
            debug_print(f"Mouse press at: {self.start_point.x()}, {self.start_point.y()}")
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
            debug_print(f"Mouse release at: {self.end_point.x()}, {self.end_point.y()}")
            debug_print(f"Selection rect: {self.selection_rect.x()}, {self.selection_rect.y()}, {self.selection_rect.width()}x{self.selection_rect.height()}")
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
        
        hotkey_info = QLabel("To change hotkey, edit the Config class")
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
