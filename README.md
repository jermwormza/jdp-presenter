# JDP Presenter — Python Edition

A from-scratch Python implementation replacing the author's retired Electron
prototype, using **Python 3.11+ and PySide6 (Qt for Python)**. Two native desktop
windows (Control + Output) share state directly in one process.

See [AGENTS.md](AGENTS.md) for architecture, [TODO.md](TODO.md) for the build
plan, and [CODEBASE_ANALYSIS.md](CODEBASE_ANALYSIS.md) /
[CODEBASE_EXPLORATION.md](CODEBASE_EXPLORATION.md) for the target data model.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Data

Songs and Bibles are stored at runtime in separate SQLite databases for fast,
indexed access. Existing JSON libraries are imported automatically the first
time an empty database is opened and are left in place as a rollback source.

Portable `.jdplibrary` files are ZIP archives containing songs as OpenLyrics
XML, Bibles as Zefania XML, and a versioned manifest. Private development builds
can create a local starter package explicitly:

```bash
python tools/build_starter_library.py
```

Starter packages and imported content are ignored by Git and are not included
in public installers. Users import content they are licensed to use.

When upgrading an installation that still has JSON song or Bible libraries,
the first launch can convert that existing content into the current database
format while retaining the legacy files and application settings.

On an installed Windows system, shared libraries default to
`%ProgramData%\jdp-presenter`. Per-user preferences remain in
`%APPDATA%\JDP Presenter\settings.json`. Bible, song, service, media, and
recording locations can be changed from **Settings > Libraries**; restart the app
after changing a location.

The Import dialog accepts Quelea song packs (`.qsp`) and OpenLyrics library
archives (`.zip` containing `.xml` songs), as well as individual Quelea script
and OpenLyrics XML files.

The schedule's Quick Add field searches songs and media by name and accepts
scripture references such as `Joh 1` (the whole chapter) or
`John 1:1-14 (CSB)`. When no translation is included, Quick Add uses the last
translation selected in the Scripture Browser. Use Up/Down to choose a result
and Enter to insert it after the currently selected schedule item.

The interface follows the operating system's light or dark appearance and
updates automatically when that preference changes. Scrollbars and controls
use the same styling across the Control window and dialogs.

## Windows Installer

Build the self-contained executable and Inno Setup installer from an activated
project environment:

```powershell
python build_local.py windows
```

For a release build, increment the patch version and package both artifacts:

```powershell
python build_local.py windows --release
```

Use `--release minor` or `--release major` when appropriate. Release mode updates
`app/version.py`, `pyproject.toml`, and the installer version before packaging.

The generated `build/` and `dist/` directories are ignored by Git and should not
be committed. Upload platform packages to a GitHub Release instead; GitHub allows
individual Release assets up to 2 GiB. The in-app updater checks the latest public
release from `jermwormza/jdp-presenter`, so both the repository and release must be
public for installed applications to check without credentials.

The build creates `dist\JDP Presenter\JDP Presenter.exe` and
`dist\installer\JDP-Presenter-Setup.exe`. The installer creates empty library
directories under `%ProgramData%\jdp-presenter` and never bundles Bible, song,
service, or media content.

FFmpeg is not bundled. WAV recording works without it; MP3 and M4A conversion
requires a separately installed `ffmpeg` executable on `PATH` (or the
`JDP_FFMPEG` environment variable). When FFmpeg is absent, the Windows installer
shows a page with the official download link: <https://ffmpeg.org/download.html>.

## License

JDP Presenter is licensed under the Apache License 2.0. See [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
