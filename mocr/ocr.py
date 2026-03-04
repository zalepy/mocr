import os
import io
from PIL import Image, ImageOps, ImageFilter
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QBuffer

from .config import Config

class OCREngine:
    """OCR processing engine using Tesseract"""
    
    def __init__(self):
        self._setup_tesseract()
    
    def _setup_tesseract(self):
        """Setup Tesseract OCR path if on Windows"""
        if not TESSERACT_AVAILABLE:
            return
        
        # Try configured path first
        if os.path.exists(Config.TESSERACT_PATH):
            pytesseract.pytesseract.tesseract_cmd = Config.TESSERACT_PATH
            return

        # Try common Tesseract installation paths
        possible_paths = [
            "C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
            "C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
            "C:\\Tesseract-OCR\\tesseract.exe",
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
            return "ERROR: pytesseract not installed. Install with: pip install pytesseract\\nAlso install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki"
        
        try:
            # Convert QPixmap to PIL Image
            # Save QPixmap to bytes buffer
            buffer = QBuffer()
            buffer.open(QBuffer.ReadWrite)
            image.save(buffer, "PNG")
            
            # Get bytes from buffer and convert to PIL Image
            buffer_bytes = buffer.data()
            bytes_buffer = io.BytesIO(buffer_bytes)
            pil_image = Image.open(bytes_buffer)
            
            return self.process_pil_image(pil_image, language)
            
        except Exception as e:
            return f"ERROR: OCR processing failed: {str(e)}"

    def process_file(self, file_path: str, language: str = None) -> str:
        """
        Process an image file and return extracted text.
        
        Args:
            file_path: Path to the image file
            language: OCR language code (e.g., 'eng', 'chi_sim')
        
        Returns:
            Extracted text string
        """
        if not os.path.exists(file_path):
            return f"ERROR: File not found: {file_path}"
            
        try:
            pil_image = Image.open(file_path)
            return self.process_pil_image(pil_image, language)
        except Exception as e:
            return f"ERROR: Failed to open image file: {str(e)}"

    def process_pil_image(self, pil_image: Image.Image, language: str = None) -> str:
        """
        Process a PIL Image and return extracted text.
        
        Args:
            pil_image: PIL Image object
            language: OCR language code (e.g., 'eng', 'chi_sim')
        
        Returns:
            Extracted text string
        """
        if not TESSERACT_AVAILABLE:
            return "ERROR: pytesseract not installed."
            
        if language is None:
            language = Config.LANGUAGE
            
        try:
            # Preprocessing to improve OCR accuracy
            # 1. Convert to grayscale
            processed_image = ImageOps.grayscale(pil_image)
            
            # 2. Sharpen the image
            processed_image = processed_image.filter(ImageFilter.SHARPEN)
            
            # Perform OCR
            text = pytesseract.image_to_string(processed_image, lang=language)
            
            # Clean up the text
            text = text.strip()
            
            if not text:
                return "(No text detected in the image)"
            
            return text
            
        except pytesseract.TesseractNotFoundError:
            return "ERROR: Tesseract OCR not found.\nPlease install from: https://github.com/UB-Mannheim/tesseract/wiki\nAnd ensure the path is correct in Config.TESSERACT_PATH"
        except Exception as e:
            return f"ERROR: OCR processing failed: {str(e)}"
