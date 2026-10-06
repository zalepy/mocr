# Testing Guide for Screen OCR Tool

## Setup

```bash
uv sync
# or
pip install -e . --group dev
```

Test and coverage settings live in `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`).

## Unit vs E2E

The suite is split in two:

| Suite | Location | Touches the OS? | Run with |
|---|---|---|---|
| Unit | `tests/unit/` | **Never** | `pytest` (default) |
| E2E | `tests/e2e/` | Yes: tray icon + notifications, clipboard, Tesseract | `pytest tests/e2e` |

**Unit tests** are enforced to stay isolated: `tests/unit/conftest.py` has an autouse
fixture that makes any real OS call (showing the tray icon or a window, tray
notifications, clipboard, screen grabs, subprocesses, Tesseract, registering
the global hotkey) fail with `Unit test attempted OS interaction: ...`. Mock the dependency
instead; for `ScreenOCRApp`, use the `ocr_app` / `mock_tray` fixtures.

**E2E tests** use the real system. Expect the tray icon and its "started"
notification to appear. Clipboard tests save your clipboard text and restore it
afterwards. OCR tests need Tesseract installed and are skipped otherwise.

```bash
pytest                 # unit tests only
pytest tests/e2e       # e2e tests only
pytest tests           # both
```

## Common Commands

```bash
pytest -x                                   # stop on first failure
pytest --lf                                 # rerun last failures
pytest tests/unit/test_ocr.py -v            # one file
pytest tests/e2e/test_ocr_tesseract.py::TestOCREngine::test_process_image_with_sample -v -s
pytest --cov --cov-report=term-missing      # coverage of the mocr package
pytest --cov --cov-report=html              # -> htmlcov/index.html
```

## Test Structure

### Unit (`tests/unit/`)
- `test_config.py` - configuration values, small utilities
- `test_ocr.py` - OCR engine logic with Tesseract mocked (pixmap conversion, language, error paths)
- `test_app.py` - app controller with tray mocked (hotkey wiring, tray menu, quit)
- `test_hotkey.py` - hotkey parsing and WM_HOTKEY handling with `RegisterHotKey` mocked
- `test_multimonitor_selection.py` - screen selection and coordinate mapping with mock screens
- `test_preprocess.py` - preprocessing transforms, line-height estimate and auto scale on synthetic images
- `test_eval_last.py` - `eval_last.py` CLI with the OCR engine mocked

### E2E (`tests/e2e/`)
- `test_ocr_tesseract.py` - real Tesseract on `sample.png` / `sample2.png`, OCR → clipboard workflow
- `test_clipboard.py` - real system clipboard round-trips
- `test_tray.py` - real tray icon and hotkey registration

### Sample images (`tests/e2e/`)
- `sample3.png` - white heading on a blue band over a photo; only `light_text` reads it ("huge AI news")
- `sample.png` - expected text: "Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki"
- `sample2.png` - expected text: "this is wild"

## Markers

- `e2e` - applied automatically to everything under `tests/e2e/`
- `slow`, `ocr` - OCR/sample image tests
- `clipboard` - clipboard tests

```bash
pytest tests -m "not e2e"   # same as the default unit run
pytest tests/e2e -m "not slow"
```

## Adding New Tests

1. Does the code under test reach the OS (Qt windows/tray, clipboard, screens,
   Tesseract, keyboard, subprocess)? If you can mock it, write a unit test in
   `tests/unit/`. If the point is to verify the real interaction, put it in `tests/e2e/`.
2. If a unit test fails with "attempted OS interaction", mock that call rather
   than moving the test, unless the test exists to check the real interaction.
