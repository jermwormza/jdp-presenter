"""Early splash screen for slow PyInstaller cold starts.

Show this BEFORE importing heavy modules (PySide6 stores, widgets, etc.).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QSplashScreen

from app.version import APP_VERSION


class SplashScreen(QSplashScreen):
    """Custom splash screen with progress messages."""

    def __init__(self, app: QApplication) -> None:
        print("[SPLASH] Creating splash screen...")
        # Create a simple pixmap for the splash
        pixmap = QPixmap(400, 250)
        pixmap.fill(QColor("#1e1e1e"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        font_family = app.font().family()

        # Draw app name
        font = QFont(font_family, 28, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(pixmap.rect().adjusted(0, 60, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "JDP Presenter")

        # Draw version
        font = QFont(font_family, 12)
        painter.setFont(font)
        painter.setPen(QColor("#888888"))
        painter.drawText(
            pixmap.rect().adjusted(0, 110, 0, 0),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            f"Version {APP_VERSION}",
        )

        # Draw loading text area
        font = QFont(font_family, 11)
        painter.setFont(font)
        painter.setPen(QColor("#aaaaaa"))
        painter.drawText(pixmap.rect().adjusted(0, 180, 0, -20), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, "Loading...")

        painter.end()

        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        self.setMask(pixmap.mask())

        self._message_label = QLabel("Initializing...", self)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        message_font = self._message_label.font()
        message_font.setPointSize(11)
        self._message_label.setFont(message_font)
        self._message_label.setStyleSheet("color: #aaaaaa; padding-bottom: 20px;")
        self._message_label.setGeometry(0, 170, 400, 50)

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setGeometry(40, 218, 320, 8)
        self._progress_bar.hide()

        print("[SPLASH] Calling show()...")
        self.show()
        print("[SPLASH] Calling processEvents()...")
        app.processEvents()  # Force immediate paint
        print("[SPLASH] Splash shown!")

    def show_message(self, message: str) -> None:
        """Update the loading message and repaint."""
        print(f"[SPLASH] Message: {message}")
        self._message_label.setText(message)
        self.repaint()
        QApplication.processEvents()

    def start_progress(self, message: str) -> None:
        """Show an indeterminate progress indicator with a status message."""
        self._progress_bar.show()
        self.show_message(message)

    def stop_progress(self) -> None:
        """Hide the progress indicator after a blocking startup operation."""
        self._progress_bar.hide()

    def finish_loading(self, main_window) -> None:
        """Close splash and show main window."""
        print("[SPLASH] Finishing...")
        self.finish(main_window)
        self.deleteLater()


def create_splash(app: QApplication) -> SplashScreen:
    """Create and show splash screen immediately."""
    print("[SPLASH] create_splash() called")
    return SplashScreen(app)