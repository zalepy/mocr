import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QLabel, QPushButton, QSystemTrayIcon, QMenu, QAction
)
from PyQt5.QtCore import Qt, QObject, QRect, QSettings
from PyQt5.QtGui import QPixmap, QIcon, QCursor

from .config import Config
from .utils import debug_print
from .ocr import OCREngine
from .clipboard import ClipboardManager
from .hotkey import GlobalHotkey
from .ui import SelectionOverlay, ResultDialog, SettingsDialog
from .preprocess import STRATEGIES
from . import __version__

# User settings persisted across restarts, with their defaults.
# The hotkey is not here: it is still configured in Config.
PERSISTED_SETTINGS = {
    'language': Config.LANGUAGE,
    'auto_copy': True,
    'show_dialog': False,
    'show_notifications': False,
}

# Every capture is saved here (cwd = repo root under start.ps1), for re-OCR and eval_last.py
LAST_CAPTURE_FILE = "last_capture.png"

class ScreenOCRApp(QObject):
    """Main application controller"""
    
    def __init__(self, settings_store: Optional[QSettings] = None):
        super().__init__()
        
        # Store captured screenshots
        self.screens_data = []
        
        # Settings (persisted via QSettings: HKCU\Software\mocr on Windows)
        self.settings_store = settings_store if settings_store is not None else QSettings("mocr", "Screen OCR")
        self.settings = {'hotkey': Config.HOTKEY}
        self.settings.update(self._load_settings())
        Config.LANGUAGE = self.settings['language']
        
        # OCR Engine
        self.ocr_engine = OCREngine()
        
        # Selection overlay (will be created when needed)
        self.overlay: Optional[SelectionOverlay] = None
        
        # Control window (backup UI if tray doesn't work)
        self.control_window: Optional[QMainWindow] = None
        
        # System-wide capture hotkey (registered in _setup_hotkey)
        self.hotkey: Optional[GlobalHotkey] = None
        
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
        
        # Re-run OCR on the saved capture with another preprocessing strategy
        reocr_menu = tray_menu.addMenu("🔁 Re-OCR last capture with")
        for strategy in STRATEGIES:
            label = strategy.label
            if strategy.name == Config.OCR_STRATEGY:
                label += "  (default)"
            action = QAction(label, reocr_menu)
            action.triggered.connect(lambda _checked=False, name=strategy.name: self.reocr_last_capture(name))
            reocr_menu.addAction(action)
        
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
        debug_print(f"Tray activated: {reason_name}")
        
        if reason == QSystemTrayIcon.DoubleClick or reason == QSystemTrayIcon.Trigger:
            # Left-click or double-click - start capture
            debug_print("  → Capturing screen")
            self.start_capture()
        elif reason == QSystemTrayIcon.Context:
            # Right-click - show menu at cursor position
            debug_print("  → Showing context menu")
            menu = self.tray_icon.contextMenu()
            if menu:
                menu.popup(QCursor.pos())
        else:
            # Unknown activation - show control panel as fallback
            debug_print("  → Showing control panel (fallback)")
            window = self._create_control_window()
            window.show()
            window.raise_()
            window.activateWindow()
    
    def _setup_hotkey(self):
        """Register the system-wide capture hotkey; warn via the tray if it is taken"""
        self.hotkey = GlobalHotkey(Config.HOTKEY, parent=self)
        self.hotkey.activated.connect(self.start_capture)
        if not self.hotkey.register():
            self.tray_icon.showMessage(
                "Hotkey Unavailable",
                f"Could not register {Config.HOTKEY} (another application may be using it).\n"
                "Use the tray icon to capture.",
                QSystemTrayIcon.Warning,
                5000
            )

    def _unregister_hotkey(self):
        if self.hotkey is not None:
            self.hotkey.unregister()

    def _capture_screen_region(self, rect: QRect) -> QPixmap:
        """Capture a specific region of the screen"""
        screens = QApplication.screens()
        
        if not screens:
            screen = QApplication.primaryScreen()
            return screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())
        
        debug_print(f"\nSelection rect: x={rect.x()}, y={rect.y()}, w={rect.width()}, h={rect.height()}")
        
        # Find the screen with the MAXIMUM overlap with the selection rect
        best_screen = None
        max_overlap = 0
        
        for idx, screen in enumerate(screens):
            screen_geo = screen.geometry()
            # Get the intersection between screen and selection
            intersection = screen_geo.intersected(rect)
            
            if not intersection.isNull():
                # Calculate overlap area
                overlap_area = intersection.width() * intersection.height()
                debug_print(f"  Screen {idx} (geo: {screen_geo.x()},{screen_geo.y()} {screen_geo.width()}x{screen_geo.height()}): overlap={overlap_area} sq pixels")
                
                if overlap_area > max_overlap:
                    max_overlap = overlap_area
                    best_screen = screen
        
        # If no intersection, try to find closest screen
        if best_screen is None:
            debug_print("No direct intersection. Finding closest screen...")
            
            # Find screen closest to selection center
            selection_center_x = rect.x() + rect.width() // 2
            min_distance = float('inf')
            
            for idx, screen in enumerate(screens):
                screen_geo = screen.geometry()
                screen_center_x = screen_geo.x() + screen_geo.width() // 2
                distance = abs(selection_center_x - screen_center_x)
                debug_print(f"  Screen {idx} center: {screen_center_x}, distance: {distance}")
                
                if distance < min_distance:
                    min_distance = distance
                    best_screen = screen
        
        if best_screen is None:
            # No screens found at all
            debug_print("ERROR: No screens found, using primary screen")
            best_screen = QApplication.primaryScreen()
        
        screen_geo = best_screen.geometry()
        debug_print(f"✓ Capturing from screen at ({screen_geo.x()}, {screen_geo.y()})")
        
        # Calculate offsets relative to the selected screen
        pixmap = best_screen.grabWindow(0,
            rect.x() - screen_geo.x(),
            rect.y() - screen_geo.y(),
            rect.width(),
            rect.height()
        )
        return pixmap
    
    def start_capture(self):
        """Start the screen capture process"""
        # Capture full screen before showing overlay
        self.screens_data = []
        screens = QApplication.screens()
        for screen in screens:
            pixmap = screen.grabWindow(0)
            self.screens_data.append({
                'pixmap': pixmap,
                'geometry': screen.geometry()
            })
        
        # A fresh overlay window every time: a reused one can keep stale screen
        # data after a display change (e.g. monitors waking from power saving)
        # and then shows off-screen, visible only as a taskbar entry.
        if self.overlay is not None:
            self.overlay.hide()
            self.overlay.deleteLater()
        self.overlay = SelectionOverlay(self.screens_data)
        self.overlay.selection_made.connect(self._on_selection_made)
        self.overlay.selection_cancelled.connect(self._on_selection_cancelled)
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
        
        # Save captured image for re-OCR / eval_last.py
        # Closed question (2026-10-06): every capture is written to disk on
        # purpose. The privacy trade-off is known and accepted; don't gate it.
        try:
            capture_save_path = Path.cwd() / LAST_CAPTURE_FILE
            captured_pixmap.save(str(capture_save_path), "PNG")
            debug_print(f"✓ Screen capture saved to: {capture_save_path}")
        except Exception as e:
            debug_print(f"Warning: Failed to save capture image: {e}")
        
        # Perform OCR
        language = self.settings.get('language', Config.LANGUAGE)
        ocr_text = self.ocr_engine.process_image(captured_pixmap, language)
        self._deliver_result(ocr_text)
    
    def reocr_last_capture(self, strategy_name: str):
        """Run OCR again on the saved last capture with another preprocessing strategy"""
        capture_path = Path.cwd() / LAST_CAPTURE_FILE
        if not capture_path.exists():
            self.tray_icon.showMessage(
                "No Capture",
                "No saved capture to re-OCR yet. Capture a region first.",
                QSystemTrayIcon.Information,
                2000
            )
            return
        
        language = self.settings.get('language', Config.LANGUAGE)
        debug_print(f"Re-OCR {capture_path} with strategy: {strategy_name}")
        ocr_text = self.ocr_engine.process_file(str(capture_path), language, strategy_name)
        if self._deliver_result(ocr_text):
            # Always show a preview: the point of re-OCR is comparing results
            preview = ocr_text if len(ocr_text) <= 200 else ocr_text[:200] + "…"
            self.tray_icon.showMessage(
                f"Re-OCR: {strategy_name}",
                preview,
                QSystemTrayIcon.Information,
                5000
            )
    
    def _deliver_result(self, ocr_text: str) -> bool:
        """Store, copy and show an OCR result per settings; False if OCR failed"""
        self.last_result = ocr_text
        
        # Check for errors
        if ocr_text.startswith("ERROR"):
            self.tray_icon.showMessage(
                "OCR Error",
                ocr_text,
                QSystemTrayIcon.Critical,
                5000
            )
            return False
        
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
        return True
    
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
        self._save_settings()
    
    def _load_settings(self) -> dict:
        """Read persisted settings, falling back to defaults"""
        loaded = {}
        for key, default in PERSISTED_SETTINGS.items():
            loaded[key] = self.settings_store.value(key, default, type=type(default))
        # Ignore a stored language that is no longer offered
        if loaded['language'] not in Config.SUPPORTED_LANGUAGES.values():
            loaded['language'] = PERSISTED_SETTINGS['language']
        return loaded
    
    def _save_settings(self):
        """Persist current settings"""
        for key in PERSISTED_SETTINGS:
            self.settings_store.setValue(key, self.settings[key])
        self.settings_store.sync()
    
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
        
        self._unregister_hotkey()
        
        self.tray_icon.hide()
        QApplication.quit()
        print("✓ Application closed")

def main():
    """Main entry point"""
    print("=" * 60)
    print(f"Screen OCR Tool v{__version__}")
    print("=" * 60)
    
    # High DPI support
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray
    
    # Set application info
    app.setApplicationName("Screen OCR Tool")
    app.setApplicationVersion(__version__)
    
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
