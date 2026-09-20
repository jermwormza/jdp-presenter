"""Recording indicator widget with elapsed time, VU meter, and pause/resume button."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QWidget, QLabel

from app.utils.icons import pause_icon, record_icon


class RecordingIndicatorWidget(QWidget):
    """A widget showing recording status: elapsed time, VU meter, and pause/resume control."""

    pause_requested = Signal()
    resume_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._elapsed_ms = 0
        self._level = 0.0
        self._paused = False
        self._recording = False

        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(8)

        # Elapsed time label
        self._time_label = QLabel("00:00")
        self._time_label.setFont(QFont("Monospace", 11))
        self._time_label.setStyleSheet("color: #e0e0e0;")
        self._time_label.setFixedWidth(50)
        layout.addWidget(self._time_label)

        # VU meter (custom painted)
        self._vu_widget = _VUMeterWidget()
        self._vu_widget.setFixedSize(60, 16)
        layout.addWidget(self._vu_widget)

        # Pause/Resume button
        self._pause_btn = QPushButton()
        self._pause_btn.setFixedSize(24, 24)
        self._pause_btn.setIconSize(self._pause_btn.size())
        self._pause_btn.setToolTip("Pause Recording")
        self._pause_btn.clicked.connect(self._on_pause_clicked)
        self._pause_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 3px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        layout.addWidget(self._pause_btn)

        self._update_pause_button()

    def _on_pause_clicked(self) -> None:
        if self._paused:
            self.resume_requested.emit()
        else:
            self.pause_requested.emit()

    def _update_pause_button(self) -> None:
        if self._paused:
            self._pause_btn.setIcon(record_icon())  # Use record icon as "resume"
            self._pause_btn.setToolTip("Resume Recording")
        else:
            self._pause_btn.setIcon(pause_icon())
            self._pause_btn.setToolTip("Pause Recording")

    # Public API -------------------------------------------------------------

    def set_elapsed_ms(self, ms: int) -> None:
        self._elapsed_ms = ms
        total_seconds = ms // 1000
        minutes, seconds = divmod(total_seconds, 60)
        self._time_label.setText(f"{minutes:02d}:{seconds:02d}")

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, level))
        self._vu_widget.set_level(self._level)

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._update_pause_button()

    def set_recording(self, recording: bool) -> None:
        self._recording = recording
        if not recording:
            self._paused = False
        self._update_pause_button()
        self._vu_widget.set_active(recording)

    def setVisible(self, visible: bool) -> None:
        super().setVisible(visible)
        if not visible:
            self._elapsed_ms = 0
            self._level = 0.0
            self._paused = False
            self._recording = False
            self._time_label.setText("00:00")
            self._vu_widget.set_level(0.0)
            self._vu_widget.set_active(False)
            self._update_pause_button()


class _VUMeterWidget(QWidget):
    """A simple horizontal VU meter bar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._level = 0.0
        self._active = False
        self.setFixedHeight(16)

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, level))
        self.update()

    def set_active(self, active: bool) -> None:
        self._active = active
        if not active:
            self._level = 0.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)

        # Background
        bg_color = QColor("#3a3a3a") if self._active else QColor("#2a2a2a")
        painter.fillRect(rect, bg_color)
        painter.setPen(QPen(QColor("#444"), 1))
        painter.drawRect(rect)

        # Level bar
        if self._level > 0 and self._active:
            level_width = int(rect.width() * self._level)
            level_rect = rect.adjusted(0, 0, -(rect.width() - level_width), 0)

            # Color based on level (green -> yellow -> red)
            if self._level < 0.6:
                color = QColor("#4caf50")  # green
            elif self._level < 0.85:
                color = QColor("#ffc107")  # yellow
            else:
                color = QColor("#f44336")  # red

            painter.fillRect(level_rect, color)