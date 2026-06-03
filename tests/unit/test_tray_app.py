"""Unit tests for the TrayApp class.

Tests icon generation and tooltip text without requiring GUI dependencies.
"""

from unittest.mock import patch, MagicMock

from src.config import Config


class TestTrayAppIconImage:
    """Tests for TrayApp._create_icon_image()."""

    def _create_tray_app(self):
        """Create a TrayApp instance with mocked dependencies."""
        with patch("src.tray_app.pystray"), \
             patch("src.tray_app.SchedulerThread") as mock_st:
            mock_st.return_value = MagicMock()
            from src.tray_app import TrayApp
            return TrayApp(Config())

    def test_running_icon_is_64x64_rgba(self):
        """Verify running icon returns a 64x64 RGBA image."""
        app = self._create_tray_app()
        image = app._create_icon_image(running=True)

        assert image.size == (64, 64)
        assert image.mode == "RGBA"

    def test_running_icon_has_green_center(self):
        """Verify running icon has green color at center pixel."""
        app = self._create_tray_app()
        image = app._create_icon_image(running=True)

        center_pixel = image.getpixel((32, 32))
        assert center_pixel == (0, 200, 0, 255)

    def test_stopped_icon_is_64x64_rgba(self):
        """Verify stopped icon returns a 64x64 RGBA image."""
        app = self._create_tray_app()
        image = app._create_icon_image(running=False)

        assert image.size == (64, 64)
        assert image.mode == "RGBA"

    def test_stopped_icon_has_gray_center(self):
        """Verify stopped icon has gray color at center pixel."""
        app = self._create_tray_app()
        image = app._create_icon_image(running=False)

        center_pixel = image.getpixel((32, 32))
        assert center_pixel == (128, 128, 128, 255)


class TestTrayAppTooltip:
    """Tests for TrayApp._get_tooltip_text()."""

    def test_tooltip_when_running_with_next_time(self):
        """Verify tooltip shows next run time when scheduler is running."""
        with patch("src.tray_app.pystray"), \
             patch("src.tray_app.SchedulerThread") as mock_st_cls:
            mock_st = MagicMock()
            mock_st.is_running.return_value = True
            mock_st.get_next_run_time.return_value = "6:00 AM"
            mock_st_cls.return_value = mock_st

            from src.tray_app import TrayApp
            app = TrayApp(Config())

            text = app._get_tooltip_text()
            assert text == "River Notify - Next run: 6:00 AM"

    def test_tooltip_when_running_no_next_time(self):
        """Verify tooltip shows 'Running' when no next time available."""
        with patch("src.tray_app.pystray"), \
             patch("src.tray_app.SchedulerThread") as mock_st_cls:
            mock_st = MagicMock()
            mock_st.is_running.return_value = True
            mock_st.get_next_run_time.return_value = None
            mock_st_cls.return_value = mock_st

            from src.tray_app import TrayApp
            app = TrayApp(Config())

            text = app._get_tooltip_text()
            assert text == "River Notify - Running"

    def test_tooltip_when_stopped(self):
        """Verify tooltip shows 'Stopped' when scheduler is not running."""
        with patch("src.tray_app.pystray"), \
             patch("src.tray_app.SchedulerThread") as mock_st_cls:
            mock_st = MagicMock()
            mock_st.is_running.return_value = False
            mock_st_cls.return_value = mock_st

            from src.tray_app import TrayApp
            app = TrayApp(Config())

            text = app._get_tooltip_text()
            assert text == "River Notify - Stopped"
