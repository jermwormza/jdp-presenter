from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSplitter, QWidget

from app.utils.window_state import (
    encode_geometry,
    encode_splitter_state,
    restore_geometry,
    restore_splitter_state,
)


class WindowStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_window_geometry_round_trip_restores_position_and_size(self) -> None:
        window = QWidget()
        window.setGeometry(80, 90, 640, 480)
        encoded = encode_geometry(window)
        window.setGeometry(10, 20, 300, 200)

        restore_geometry(window, encoded)

        self.assertEqual(window.geometry().getRect(), (80, 90, 640, 480))

    def test_splitter_state_round_trip_restores_layout(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(QWidget())
        splitter.addWidget(QWidget())
        splitter.resize(600, 200)
        splitter.setSizes([180, 420])
        expected_sizes = splitter.sizes()
        encoded = encode_splitter_state(splitter)
        splitter.setSizes([420, 180])

        restore_splitter_state(splitter, encoded)

        self.assertEqual(splitter.sizes(), expected_sizes)


if __name__ == "__main__":
    unittest.main()