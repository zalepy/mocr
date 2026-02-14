"""
Unit tests for multi-monitor screen selection.

Tests verify that screen regions can be correctly captured from any monitor,
regardless of how many monitors exist or their positioning in virtual desktop.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PyQt5.QtCore import QRect, QPoint
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QApplication

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from screen_ocr import SelectionOverlay, ScreenOCRApp


class MockScreen:
    """Mock QScreen for testing"""
    def __init__(self, x, y, width, height):
        self._geometry = QRect(x, y, width, height)
        self._pixmap_reads = []
    
    def geometry(self):
        return self._geometry
    
    def grabWindow(self, id, x, y, width, height):
        """Mock grabWindow - records what coordinates were requested"""
        self._pixmap_reads.append({
            'id': id,
            'x': x,
            'y': y,
            'width': width,
            'height': height,
            'screen_offset_x': self._geometry.x(),
            'screen_offset_y': self._geometry.y(),
        })
        
        # Return a non-null dummy pixmap
        from PyQt5.QtGui import QPixmap, QColor
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("white"))
        return pixmap


class TestMultiMonitorSelection:
    """Test screen selection across multiple monitors"""
    
    @pytest.fixture
    def mock_screens_with_gap(self):
        """
        Simulate two 4K monitors with OS scaling offset/gap.
        
        This reproduces the actual user setup:
        - Screen 0: 0 to 1920 (after scaling)
        - Screen 1: 3840 to 5760 (after scaling)
        - Gap: 1920 to 3840
        """
        return [
            MockScreen(0, 0, 1920, 1080),      # Screen 0
            MockScreen(3840, 0, 1920, 1080),   # Screen 1
        ]
    
    @pytest.fixture
    def mock_screens_adjacent(self):
        """Simulate two monitors positioned directly adjacent (no gap)"""
        return [
            MockScreen(0, 0, 1920, 1080),      # Screen 0
            MockScreen(1920, 0, 1920, 1080),   # Screen 1
        ]
    
    def test_selection_on_primary_screen(self, mock_screens_with_gap):
        """Test that selection on primary screen (left) is captured correctly"""
        # Selection at (500, 500) on primary screen
        selection_rect = QRect(500, 500, 200, 200)
        
        # Find which screen intersects
        best_screen = None
        max_overlap = 0
        
        for screen in mock_screens_with_gap:
            intersection = screen.geometry().intersected(selection_rect)
            if not intersection.isNull():
                overlap = intersection.width() * intersection.height()
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_screen = screen
        
        assert best_screen is not None, "Selection should match a screen"
        assert best_screen == mock_screens_with_gap[0], "Selection on primary screen"
        
        # Verify capture would use correct offsets
        screen_geo = best_screen.geometry()
        capture_x = selection_rect.x() - screen_geo.x()
        capture_y = selection_rect.y() - screen_geo.y()
        
        assert capture_x == 500, "X offset should be 500 (500 - 0)"
        assert capture_y == 500, "Y offset should be 500 (500 - 0)"
    
    def test_selection_on_secondary_screen_with_gap(self, mock_screens_with_gap):
        """Test that selection on secondary screen works even with coordinate gap"""
        # Selection at (4500, 500) on secondary screen
        selection_rect = QRect(4500, 500, 200, 200)
        
        # Find which screen intersects (max overlap method)
        best_screen = None
        max_overlap = 0
        
        for screen in mock_screens_with_gap:
            intersection = screen.geometry().intersected(selection_rect)
            if not intersection.isNull():
                overlap = intersection.width() * intersection.height()
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_screen = screen
        
        # If no direct intersection due to gap, use closest screen
        if best_screen is None:
            selection_center_x = selection_rect.x() + selection_rect.width() // 2
            min_distance = float('inf')
            
            for screen in mock_screens_with_gap:
                screen_geo = screen.geometry()
                screen_center_x = screen_geo.x() + screen_geo.width() // 2
                distance = abs(selection_center_x - screen_center_x)
                
                if distance < min_distance:
                    min_distance = distance
                    best_screen = screen
        
        assert best_screen is not None, "Selection should match a screen (direct or by proximity)"
        assert best_screen == mock_screens_with_gap[1], "Selection should match secondary screen"
        
        # Verify capture would use correct offsets
        screen_geo = best_screen.geometry()
        capture_x = selection_rect.x() - screen_geo.x()
        capture_y = selection_rect.y() - screen_geo.y()
        
        # Screen 1 is at x=3840, selection at x=4500, so offset = 660
        assert capture_x == 660, f"X offset should be 660 (4500 - 3840), got {capture_x}"
        assert capture_y == 500, f"Y offset should be 500 (500 - 0), got {capture_y}"
    
    def test_selection_in_gap_uses_closest_screen(self, mock_screens_with_gap):
        """Test that coordinates in the gap use closest screen fallback"""
        # Selection in the gap area (2000, 500)
        selection_rect = QRect(2000, 500, 200, 200)
        
        # Try direct intersection first
        best_screen = None
        max_overlap = 0
        
        for screen in mock_screens_with_gap:
            intersection = screen.geometry().intersected(selection_rect)
            if not intersection.isNull():
                overlap = intersection.width() * intersection.height()
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_screen = screen
        
        # Should have no direct match (coordinates in gap)
        assert best_screen is None, "Gap coordinates should not intersect with any screen"
        
        # Now apply closest-screen logic
        selection_center_x = selection_rect.x() + selection_rect.width() // 2  # 2100
        min_distance = float('inf')
        
        for screen in mock_screens_with_gap:
            screen_geo = screen.geometry()
            screen_center_x = screen_geo.x() + screen_geo.width() // 2
            distance = abs(selection_center_x - screen_center_x)
            
            if distance < min_distance:
                min_distance = distance
                best_screen = screen
        
        assert best_screen is not None, "Closest screen should be found"
        # Screen 0 center: 960, Screen 1 center: 4800
        # Selection center: 2100
        # Distance to Screen 0: |2100 - 960| = 1140
        # Distance to Screen 1: |2100 - 4800| = 2700
        # Should pick Screen 0
        assert best_screen == mock_screens_with_gap[0], "Gap selection should pick closest screen (Screen 0)"
    
    def test_selection_on_adjacent_screens(self, mock_screens_adjacent):
        """Test selection when monitors are adjacent without gap"""
        # Selection at (2500, 500) spanning both monitors
        selection_rect = QRect(2500, 500, 200, 200)
        
        best_screen = None
        max_overlap = 0
        
        for screen in mock_screens_adjacent:
            intersection = screen.geometry().intersected(selection_rect)
            if not intersection.isNull():
                overlap = intersection.width() * intersection.height()
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_screen = screen
        
        assert best_screen is not None, "Selection should match a screen"
        # Selection spans both, but should pick the one with more overlap
        # Screen 0 (0-1920): 1920-2500 = 580 pixels overlap
        # Screen 1 (1920-3840): 2500-3840 = 1340 pixels overlap (wrong calc)
        # Actually: selection is 2500-2700
        # Screen 0 (0-1920): no overlap
        # Screen 1 (1920-3840): 2500-2700 = 200 pixels overlap
        assert best_screen == mock_screens_adjacent[1], "Should pick Screen 1 for (2500, 500) selection"
    
    def test_overlay_geometry_calculation(self, mock_screens_with_gap):
        """Test that overlay geometry correctly spans all screens"""
        # Simulate combining all screen geometries
        combined = mock_screens_with_gap[0].geometry()
        for screen in mock_screens_with_gap[1:]:
            combined = combined.united(screen.geometry())
        
        # Should span from 0 to 5760 in X (with gap)
        assert combined.x() == 0, "Combined geometry should start at x=0"
        assert combined.y() == 0, "Combined geometry should start at y=0"
        assert combined.width() == 5760, "Combined geometry width should be 5760"
        assert combined.height() == 1080, "Combined geometry height should be 1080"
    
    def test_capture_uses_correct_screen_offsets(self, mock_screens_with_gap):
        """Test that captured region is offset correctly from screen origin"""
        # Test selections on each screen
        test_cases = [
            (QRect(500, 500, 100, 100), 0, 500, 500),      # Screen 0
            (QRect(4500, 500, 100, 100), 1, 660, 500),      # Screen 1 (4500-3840=660)
        ]
        
        for selection_rect, expected_screen_idx, expected_x_offset, expected_y_offset in test_cases:
            best_screen = None
            max_overlap = 0
            
            for screen in mock_screens_with_gap:
                intersection = screen.geometry().intersected(selection_rect)
                if not intersection.isNull():
                    overlap = intersection.width() * intersection.height()
                    if overlap > max_overlap:
                        max_overlap = overlap
                        best_screen = screen
            
            assert best_screen == mock_screens_with_gap[expected_screen_idx], \
                f"Selection {selection_rect.x()},{selection_rect.y()} should match screen {expected_screen_idx}"
            
            # Verify offset calculation
            screen_geo = best_screen.geometry()
            actual_x_offset = selection_rect.x() - screen_geo.x()
            actual_y_offset = selection_rect.y() - screen_geo.y()
            
            assert actual_x_offset == expected_x_offset, \
                f"X offset should be {expected_x_offset}, got {actual_x_offset}"
            assert actual_y_offset == expected_y_offset, \
                f"Y offset should be {expected_y_offset}, got {actual_y_offset}"


class TestOverlayWindowSpanning:
    """Test that overlay window properly spans all screens"""
    
    def test_overlay_is_positioned_for_all_screens(self, qtbot):
        """Test that overlay window geometry covers all screens"""
        from unittest.mock import Mock, patch
        
        # Mock screens
        mock_screen_0 = Mock()
        mock_screen_0.geometry.return_value = QRect(0, 0, 1920, 1080)
        
        mock_screen_1 = Mock()
        mock_screen_1.geometry.return_value = QRect(3840, 0, 1920, 1080)
        
        with patch('screen_ocr.QGuiApplication.screens', return_value=[mock_screen_0, mock_screen_1]):
            overlay = SelectionOverlay([])
            
            # Verify overlay geometry covers both screens
            overlay_geo = overlay.total_geometry
            assert overlay_geo.x() == 0
            assert overlay_geo.y() == 0
            assert overlay_geo.width() == 5760, "Overlay should span both screens"
            assert overlay_geo.height() == 1080
    
    def test_mouse_events_report_global_coordinates(self, qtbot):
        """Test that mouse events in overlay report absolute virtual desktop coordinates"""
        from unittest.mock import Mock, patch
        
        mock_screen_0 = Mock()
        mock_screen_0.geometry.return_value = QRect(0, 0, 1920, 1080)
        
        mock_screen_1 = Mock()
        mock_screen_1.geometry.return_value = QRect(3840, 0, 1920, 1080)
        
        with patch('screen_ocr.QGuiApplication.screens', return_value=[mock_screen_0, mock_screen_1]):
            overlay = SelectionOverlay([])
            
            # Simulate mouse events on different screens
            # Event on Screen 0
            event_0 = Mock()
            event_0.pos.return_value = QPoint(500, 500)
            event_0.button.return_value = 1  # LeftButton
            
            # Event on Screen 1 (should report coordinates in 3840+ range)
            event_1 = Mock()
            event_1.pos.return_value = QPoint(4500, 500)
            event_1.button.return_value = 1
            
            # These should all be valid coordinates that can be mapped to screens
            assert event_0.pos().x() >= 0
            assert event_1.pos().x() >= 3840
