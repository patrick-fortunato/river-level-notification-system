"""Windowless system tray entry point for the River Level Notification System.

Launch this file to run the scheduler as a system tray icon with no
visible console window. Uses pythonw.exe via the .pyw extension.

Right-click the tray icon for: Run Now, Start/Stop Scheduler, Quit.
"""

from src.config import Config
from src.tray_app import TrayApp


def main() -> None:
    config = Config()
    app = TrayApp(config)
    app.run()


if __name__ == "__main__":
    main()
