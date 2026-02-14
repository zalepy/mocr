# Testing Guide for Screen OCR Tool

This guide explains how to run the test suite with coverage reporting.

## Setup

Install test dependencies:

```bash
pip install -r requirements.txt
# or
pip install pytest pytest-cov pytest-qt
```

## Running Tests

### Quick Start

Run all tests with coverage:

```bash
pytest -v --cov=screen_ocr --cov-report=html
```

Or using the provided test runner:

```bash
python run_tests.py
```

### Common Test Commands

**Run all tests verbosely:**
```bash
pytest -v
```

**Run only fast tests (skip OCR processing):**
```bash
pytest -v -m "not slow"
python run_tests.py --fast
```

**Run only OCR-related tests:**
```bash
pytest -v -m ocr
python run_tests.py --only-ocr
```

**Run specific test file:**
```bash
pytest tests/test_screen_ocr.py -v
```

**Run specific test class:**
```bash
pytest tests/test_screen_ocr.py::TestOCREngine -v
```

**Run specific test:**
```bash
pytest tests/test_screen_ocr.py::TestOCREngine::test_process_image_with_sample -v
```

**Run without coverage reporting:**
```bash
pytest -v --no-cov
python run_tests.py --no-coverage
```

## Coverage Reports

Coverage is automatically generated in multiple formats:

### HTML Report
```bash
pytest --cov=screen_ocr --cov-report=html
# Open: htmlcov/index.html
```

### Terminal Report
```bash
pytest --cov=screen_ocr --cov-report=term-missing
```

### XML Report (for CI/CD)
```bash
pytest --cov=screen_ocr --cov-report=xml
```

## Test Structure

### Test Files

- **`tests/test_screen_ocr.py`** - Main test suite with:
  - `TestConfig` - Configuration validation tests
  - `TestOCREngine` - OCR processing tests
  - `TestClipboardManager` - Clipboard operation tests
  - `TestWindowsIntegration` - Windows-specific utilities tests
  - `TestIntegration` - End-to-end workflow tests

### Test Requirements

- **Sample Image**: `tests/sample.png` - Used for OCR testing
  - Expected detected text: "Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki"
  - Required for: OCR processing tests
  - Skip if: Tesseract OCR is not installed

- **Tesseract OCR**: Required for OCR-related tests
  - Tests are automatically skipped if not available
  - Install from: https://github.com/UB-Mannheim/tesseract/wiki

## Test Markers

Tests are marked for easy filtering:

```bash
# Run only slow tests (OCR processing, which can take time)
pytest -m slow

# Skip slow tests
pytest -m "not slow"

# Run OCR-related tests
pytest -m ocr

# Run clipboard tests
pytest -m clipboard

# Run Windows-specific tests
pytest -m windows
```

## Coverage Goals

Current test coverage includes:

- ✅ **Config class**: Hotkey, languages, display settings
- ✅ **OCREngine**: Image processing with Tesseract
- ✅ **ClipboardManager**: Copy/paste operations with unicode support
- ✅ **WindowsIntegration**: Startup folder, registry, notifications
- ✅ **Integration**: Full OCR-to-clipboard workflow

Aiming for:
- **Target**: >80% code coverage
- **Critical paths**: 100% coverage
- **OCR engine**: Fully tested with sample image

## Continuous Integration

To run tests in CI/CD pipeline:

```bash
pytest --cov=screen_ocr --cov-report=xml --cov-fail-under=80
```

## Troubleshooting

### "Sample image not found"
- Ensure `tests/sample.png` exists
- Tests are skipped if missing

### "Tesseract not installed"
- OCR tests are skipped if Tesseract is not available
- Run non-OCR tests with: `pytest -m "not ocr"`

### "PyQt5 display errors"
- Some tests use `pytest-qt` which handles Qt events
- These should work in headless environments

### Performance
- First OCR run may be slow (Tesseract initialization)
- Subsequent runs are cached by OCR engine
- Use `--fast` flag to skip slow tests during development

## Development Tips

1. **Write tests while developing features**
   ```bash
   pytest -v -x  # Stop on first failure
   ```

2. **Watch for regressions**
   ```bash
   pytest -v --lf  # Run last failed tests
   ```

3. **Check coverage while developing**
   ```bash
   pytest --cov=screen_ocr --cov-report=term-missing -k "your_feature"
   ```

4. **Run specific test in isolation**
   ```bash
   pytest tests/test_screen_ocr.py::TestOCREngine::test_process_image_with_sample -v -s
   ```

## Adding New Tests

When adding new features:

1. Create test in `tests/test_screen_ocr.py`
2. Use appropriate test class or create new one
3. Add markers as needed (`@pytest.mark.slow`, etc.)
4. Ensure sample image has correct expected text
5. Run with coverage: `pytest --cov=screen_ocr`

## Example Test Template

```python
def test_my_feature():
    """Test description"""
    # Arrange
    test_input = "something"
    
    # Act
    result = some_function(test_input)
    
    # Assert
    assert result == expected_value
```
