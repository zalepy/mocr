import sys
import subprocess
from pathlib import Path

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
