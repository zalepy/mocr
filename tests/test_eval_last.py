import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import io

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval_last import main

class TestEvalLast:
    """Tests for eval_last.py script"""
    
    @patch('eval_last.OCREngine')
    @patch('pathlib.Path.exists')
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_file_exists(self, mock_stdout, mock_exists, mock_engine_class):
        """Test main functionality when file exists"""
        # Setup mocks
        mock_exists.return_value = True
        mock_engine = mock_engine_class.return_value
        mock_engine.process_file.return_value = "Detected OCR Text"
        
        # Run main
        main()
        
        # Verify
        mock_engine.process_file.assert_called_once()
        output = mock_stdout.getvalue()
        assert "Detected OCR Text" in output
        assert "Processing:" in output

    @patch('pathlib.Path.exists')
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_file_missing(self, mock_stdout, mock_exists):
        """Test main behavior when file is missing"""
        # Setup mock
        mock_exists.return_value = False
        
        # Run main
        main()
        
        # Verify
        output = mock_stdout.getvalue()
        assert "Error: Last capture file not found" in output
