"""System tray application for the River Level Notification System."""

import threading

import pystray
from PIL import Image, ImageDraw

from src.config import Config
from src.scheduler_thread import SchedulerThread


class TrayApp:
    """System tray application that manages the scheduler via a notification area icon."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._scheduler_thread = SchedulerThread(config)
        self._icon: pystray.Icon | None = None

    def run(self) -> None:
        """Start the tray app. Blocks on the main thread."""
        self._scheduler_thread.start()

        icon_image = self._create_icon_image(running=True)
        menu = self._build_menu()

        self._icon = pystray.Icon(
            name="river_notify",
            icon=icon_image,
            title=self._get_tooltip_text(),
            menu=menu,
        )
        self._icon.run()

    def on_run_now(self, icon, item) -> None:
        """Execute the pipeline immediately."""
        self._scheduler_thread.run_now()

    def on_stop(self, icon, item) -> None:
        """Stop the scheduler."""
        self._scheduler_thread.stop()
        if self._icon:
            self._icon.icon = self._create_icon_image(running=False)
            self._icon.title = self._get_tooltip_text()

    def on_start(self, icon, item) -> None:
        """Start the scheduler."""
        self._scheduler_thread.start()
        if self._icon:
            self._icon.icon = self._create_icon_image(running=True)
            self._icon.title = self._get_tooltip_text()

    def on_quit(self, icon, item) -> None:
        """Quit the application."""
        self._scheduler_thread.stop()
        if self._icon:
            self._icon.stop()

    def _create_icon_image(self, running: bool) -> Image.Image:
        """Generate a colored circle icon (green=running, gray=stopped)."""
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = (0, 200, 0, 255) if running else (128, 128, 128, 255)
        draw.ellipse([4, 4, size - 4, size - 4], fill=color)
        return image

    def _build_menu(self) -> pystray.Menu:
        """Build the right-click context menu."""
        return pystray.Menu(
            pystray.MenuItem(
                "Run Now",
                self.on_run_now,
                enabled=lambda item: not self._scheduler_thread.is_pipeline_running(),
            ),
            pystray.MenuItem(
                "Start Scheduler",
                self.on_start,
                enabled=lambda item: not self._scheduler_thread.is_running(),
            ),
            pystray.MenuItem(
                "Stop Scheduler",
                self.on_stop,
                enabled=lambda item: self._scheduler_thread.is_running(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.on_quit),
        )

    def _get_tooltip_text(self) -> str:
        """Return status-aware tooltip text."""
        if self._scheduler_thread.is_running():
            next_time = self._scheduler_thread.get_next_run_time()
            if next_time:
                return f"River Notify - Next run: {next_time}"
            return "River Notify - Running"
        return "River Notify - Stopped"
