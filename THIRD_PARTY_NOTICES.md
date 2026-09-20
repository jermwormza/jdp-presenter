# Third-Party Notices

JDP Presenter
Copyright 2026 Jeremy Pointer

JDP Presenter is licensed under the Apache License, Version 2.0. See `LICENSE`.

Binary distributions include open-source dependencies under their own licenses.
This notice is informational and does not replace those license terms.

## Runtime Dependencies

| Component | License | Project |
| --- | --- | --- |
| PySide6 / Qt for Python | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only OR commercial | https://www.qt.io/qt-for-python |
| Flask | BSD-3-Clause | https://palletsprojects.com/p/flask/ |
| Flask-SocketIO | MIT | https://github.com/miguelgrinberg/Flask-SocketIO |
| python-socketio | MIT | https://github.com/miguelgrinberg/python-socketio |
| qrcode | BSD | https://github.com/lincolnloop/python-qrcode |
| Pillow | MIT-CMU | https://python-pillow.org/ |
| Requests | Apache-2.0 | https://requests.readthedocs.io/ |
| python-sounddevice | MIT | https://python-sounddevice.readthedocs.io/ |
| NumPy | BSD-3-Clause and bundled component licenses | https://numpy.org/ |
| QtAwesome | MIT | https://github.com/spyder-ide/qtawesome |

QtAwesome packages multiple icon fonts. JDP Presenter requests Font Awesome Free
6 glyphs through QtAwesome. Font Awesome Free icons are licensed under CC BY 4.0,
fonts under SIL OFL 1.1, and code under MIT:
https://fontawesome.com/license/free

The generic application icon files in `assets/` are project assets released by
the project owner under the Apache License 2.0. They are not sourced from
QtAwesome. The runtime splash screen is drawn by application code and does not
use a third-party graphic.

## Build Dependencies

| Component | License | Project |
| --- | --- | --- |
| PyInstaller | GPL-2.0-or-later with bootloader exception | https://pyinstaller.org/ |
| py2app | MIT | https://py2app.readthedocs.io/ |

PyInstaller's bootloader exception permits distribution of applications under
licenses other than the GPL.

## Optional External Software

FFmpeg is not bundled with JDP Presenter. Users may install it separately for
MP3 and M4A conversion. FFmpeg and third-party executable builds offered from the
official download page are governed by their respective licenses:
https://ffmpeg.org/download.html

## License Texts

Authoritative license texts and notices are available from each linked project.
Binary release preparation must retain the license files distributed with the
exact dependency versions used for that release. PySide6/Qt shared libraries must
remain replaceable in binary distributions to satisfy the selected LGPL terms.
