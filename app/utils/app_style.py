"""Application-wide light/dark palette and consistent native-widget styling."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def _is_dark(app: QApplication) -> bool:
    color_scheme = app.styleHints().colorScheme()
    if color_scheme == Qt.ColorScheme.Dark:
        return True
    if color_scheme == Qt.ColorScheme.Light:
        return False
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def apply_system_theme(app: QApplication) -> None:
    """Apply a polished palette matching the operating system color scheme."""
    dark = _is_dark(app)
    colors = (
        {
            "window": "#181b20",
            "panel": "#20242b",
            "control": "#292e37",
            "raised": "#343b46",
            "text": "#f2f4f7",
            "muted": "#aeb6c2",
            "border": "#444c59",
            "accent": "#39a8d8",
            "selection": "#176b91",
            "disabled": "#747d89",
        }
        if dark
        else {
            "window": "#f4f6f8",
            "panel": "#ffffff",
            "control": "#eef1f4",
            "raised": "#dfe5ea",
            "text": "#1d252d",
            "muted": "#5e6975",
            "border": "#c4ccd4",
            "accent": "#087da8",
            "selection": "#b9e4f5",
            "disabled": "#929ba5",
        }
    )

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["control"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["control"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["selection"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(colors["muted"]))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(colors["disabled"])
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(colors["disabled"]),
    )
    app.setPalette(palette)

    app.setStyleSheet(
        f"""
        QMainWindow, QDialog {{ background: {colors['window']}; }}
        QToolBar {{
            background: {colors['panel']}; border: 0; spacing: 4px; padding: 4px 6px;
        }}
        QToolBar QToolButton, QToolBar QPushButton {{
            background: transparent; border: 1px solid transparent;
            border-radius: 4px; padding: 5px 7px;
        }}
        QToolBar QToolButton:hover, QToolBar QPushButton:hover {{
            background: {colors['control']}; border-color: {colors['border']};
        }}
        QToolBar QToolButton:pressed, QToolBar QPushButton:pressed,
        QToolBar QToolButton:checked, QToolBar QPushButton:checked {{
            background: {colors['selection']}; border-color: {colors['accent']};
        }}
        QToolBar::separator {{
            width: 1px; margin: 5px 4px; background: {colors['border']};
        }}
        QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QListWidget, QTreeWidget {{
            background: {colors['panel']}; color: {colors['text']};
            border: 1px solid {colors['border']}; border-radius: 4px;
            selection-background-color: {colors['selection']};
        }}
        QLineEdit, QComboBox {{ padding: 5px 7px; }}
        QPushButton {{
            background: {colors['control']}; color: {colors['text']};
            border: 1px solid {colors['border']}; border-radius: 4px; padding: 6px 10px;
        }}
        QPushButton:hover {{ background: {colors['raised']}; border-color: {colors['accent']}; }}
        QPushButton:pressed {{ background: {colors['selection']}; }}
        QScrollBar:vertical {{
            background: {colors['control']}; width: 12px; margin: 0; border: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {colors['muted']}; min-height: 28px; margin: 2px; border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {colors['accent']}; }}
        QScrollBar:horizontal {{
            background: {colors['control']}; height: 12px; margin: 0; border: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {colors['muted']}; min-width: 28px; margin: 2px; border-radius: 4px;
        }}
        QScrollBar::handle:horizontal:hover {{ background: {colors['accent']}; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        """
    )


def install_system_theme(app: QApplication) -> None:
    """Apply the current OS theme and follow changes made while the app is running."""
    apply_system_theme(app)
    app.styleHints().colorSchemeChanged.connect(lambda _scheme: apply_system_theme(app))