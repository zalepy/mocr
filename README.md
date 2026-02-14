# Screen OCR Tool

A Windows-like screen capture tool that performs OCR (Optical Character Recognition) on the selected region and copies the text to clipboard.

## Features

- **Windows-like Selection Interface**: Semi-transparent overlay with rectangular selection, mimicking the native `Win+Shift+S` snipping tool
- **Real-time Size Display**: Shows dimensions of selection rectangle as you drag
- **Multi-monitor Support**: Works across all connected monitors
- **System Tray Integration**: Runs quietly in the background with tray icon
- **Global Hotkey**: Press `Ctrl+Alt+Print Screen` to start capture from anywhere
- **OCR with Multiple Languages**: Supports English, Chinese, Japanese, Korean, and more
- **Auto-copy to Clipboard**: Extracted text is automatically copied
- **Result Preview Dialog**: Optional dialog to review and edit text before copying

## Requirements

- **Python 3.8+**
- **Tesseract OCR** (must be installed separately)

## Installation

### 1. Install Tesseract OCR

**Windows:**
1. Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer (recommended to install to `C:\Program Files\Tesseract-OCR\`)
3. During installation, make sure to select additional language packs if needed

**Verify Tesseract installation:**
```bash
# Check if Tesseract is in PATH
tesseract --version
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Application

```bash
python screen_ocr.py
```

## Usage

### Basic Usage

1. Run the application - it will minimize to system tray
   ```bash
   python screen_ocr.py
   ```
2. Press `Ctrl+Alt+Print Screen` to start screen capture
3. Click and drag to select a region of the screen
4. Release mouse button to capture and OCR
5. The extracted text is automatically copied to clipboard

### Debug Mode

To see detailed debug output (useful for troubleshooting):

```bash
python screen_ocr.py --debug
```

This will print information about:
- Multi-monitor detection and geometry
- Selection coordinates and screen matching
- Hotkey events
- Screen capture operations

### Alternative Methods

- **Double-click tray icon**: Start capture
- **Right-click tray icon → Capture Screen**: Start capture

### Changing Settings

Right-click the tray icon and select "Settings..." to:
- Change OCR language
- Toggle auto-copy behavior
- Toggle result dialog display

## Hotkeys

| Hotkey | Action |
|--------|--------|
| `Ctrl+Alt+Print Screen` | Start screen capture |
| `Esc` | Cancel selection |

## Supported OCR Languages

- English (eng)
- Chinese Simplified (chi_sim)
- Chinese Traditional (chi_tra)
- Japanese (jpn)
- Korean (kor)
- German (deu)
- French (fra)
- Spanish (spa)
- Russian (rus)
- Arabic (ara)

To add more languages, install additional Tesseract language packs and modify the `Config.SUPPORTED_LANGUAGES` dictionary in `screen_ocr.py`.

## Configuration

Edit the `Config` class in `screen_ocr.py` to customize:

```python
class Config:
    # Hotkey for triggering screen capture
    HOTKEY = "ctrl+alt+prtscn"
    
    # OCR Settings
    TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    LANGUAGE = "eng"  # Default OCR language
    
    # Selection overlay settings
    SELECTION_COLOR = QColor(0, 120, 215, 200)  # Windows blue
    OVERLAY_OPACITY = 0.3
```

## Troubleshooting

### Multi-monitor Issues

If the selection overlay doesn't appear on all monitors or captures from the wrong screen:

1. Run with debug mode to see monitor detection:
   ```bash
   python screen_ocr.py --debug
   ```

2. Check the output for screen geometries - they should show all your monitors

3. The tool automatically detects and handles:
   - Monitors with gaps in coordinates (common with OS scaling)
   - Different screen resolutions
   - Different refresh rates
   - Portrait/landscape orientations

### "Tesseract not found" error

1. Ensure Tesseract is installed
2. Check if the path in `Config.TESSERACT_PATH` matches your installation
3. Add Tesseract to your system PATH

### Hotkey not working

1. Make sure `keyboard` package is installed: `pip install keyboard`
2. Run the application as Administrator (required for global hotkeys on Windows)
3. Check if another application is using the same hotkey

### No text detected

1. Ensure the selected region contains clear, readable text
2. Try selecting a larger region
3. Check that the correct language is selected in settings
4. Install additional language packs for Tesseract if needed

## Alternative: Integration with Win+Shift+S

If you want to intercept Windows' native `Win+Shift+S` snipping tool, you have two options:

### Option 1: AutoHotkey Script

Create an AutoHotkey script that redirects `Win+Shift+S` to your Python script:

```autohotkey
; Redirect Win+Shift+S to run the Python script
#S::
Run, python "C:\path\to\screen_ocr.py" --capture
return
```

### Option 2: Replace Snipping Tool

1. Disable the built-in snipping tool in Windows Settings
2. Use a tool like AutoHotkey to bind `Win+Shift+S` to this application

## File Structure

```
screen-ocr-tool/
├── screen_ocr.py      # Main application
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

## License

MIT License - Feel free to modify and distribute.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.
