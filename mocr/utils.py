import sys
import os
import subprocess
from pathlib import Path

# Debug flag
DEBUG = "--debug" in sys.argv

# Windows-specific clipboard enhancements
try:
    import win32registry
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

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
            f.write(f'@echo off\\npythonw \"{script_path}\"\\n')
        
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
                "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                0,
                win32registry.KEY_SET_VALUE
            )
            
            if enabled:
                win32registry.SetValueEx(key, name, 0, win32registry.REG_SZ, f'pythonw \"{script_path}\"')
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
        # Not using WIN32_AVAILABLE here as it's PowerShell based
        try:
            # Use PowerShell for toast notifications
            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            
            $template = @\"
            <toast>
                <visual>
                    <binding template=\"ToastText02\">
                        <text id=\"1\">{title}</text>
                        <text id=\"2\">{message}</text>
                    </binding>
                </visual>
            </toast>
\"@
            
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
