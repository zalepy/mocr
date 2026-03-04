from PyQt5.QtGui import QColor

class Config:
    """Application configuration"""
    # Hotkey for triggering screen capture
    HOTKEY = "ctrl+alt+prtscn"
    
    # OCR Settings
    TESSERACT_PATH = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"  # Default Windows path
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
        "Bulgarian": "bul",
    }
