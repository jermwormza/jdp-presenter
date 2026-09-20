from __future__ import annotations

import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.models.bible import BibleBook, BibleChapter, BibleTranslation, BibleVerse
from app.models.service import Service
from app.models.song import Song, Verse
from app.models.theme import default_theme
from app.persistence import bible_repo, song_repo
from app.persistence import service_repo
from app.persistence.library_package import (
    convert_legacy_library,
    detect_legacy_library,
    export_library,
    import_library,
    replace_with_starter_library,
)
from app.utils.importers.openlyrics_songs import (
    parse_openlyrics_archive,
    parse_openlyrics_xml,
    serialize_openlyrics,
)
from app.utils.importers.quelea_songs import parse_quelea_song_pack
from app.utils.importers.zefania_bible import parse_zefania_xml, serialize_zefania
from app.widgets.recording_options_dialog import (
    RecordingOptionsDialog,
    default_recording_name,
    sanitize_recording_name,
)


class StandardFormatTests(unittest.TestCase):
    def test_recording_name_uses_sanitized_service_name(self) -> None:
        self.assertEqual(default_recording_name('Sunday: AM / "Communion"?'), "Sunday_ AM _ _Communion__")
        self.assertEqual(sanitize_recording_name("CON"), "CON_")
        self.assertEqual(sanitize_recording_name("Service. "), "Service_")

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_schedule_name_is_fixed_and_remembering_disables_future_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            values: dict[str, object] = {"recordingOutputDir": temporary_directory}

            class SettingsStub:
                def get(self, key: str, default=None):
                    return values.get(key, default)

                def set(self, key: str, value: object) -> None:
                    values[key] = value

            dialog = RecordingOptionsDialog(
                SettingsStub(),  # type: ignore[arg-type]
                default_name='Sunday: AM / "Communion"?',
            )
            dialog._remember_check.setChecked(True)
            dialog._on_accept()

        self.assertTrue(dialog._filename_edit.isReadOnly())
        self.assertEqual(dialog.file_name(), "Sunday_ AM _ _Communion__")
        self.assertFalse(values["recordingPromptForOptions"])

    def test_openlyrics_round_trip_preserves_supported_fields(self) -> None:
        song = Song(
            id="song-1",
            title="Example Song",
            author="First Author; Second Author",
            copyright="2026 Example",
            ccli="12345",
            key="G",
            tempo=120,
            verses=[Verse("v1", "First line\n\nThird line"), Verse("c1", "Chorus")],
            verse_order=["v1", "c1"],
        )

        restored = parse_openlyrics_xml(serialize_openlyrics(song))

        for field in ("title", "author", "copyright", "ccli", "key", "tempo", "verses", "verse_order"):
            self.assertEqual(getattr(restored, field), getattr(song, field))

    def test_zefania_round_trip_preserves_scripture(self) -> None:
        bible = BibleTranslation(
            id="bible-1",
            name="Example Bible",
            abbreviation="EXB",
            language="en",
            books=[
                BibleBook(
                    number=1,
                    name="Genesis",
                    chapters=[BibleChapter(1, [BibleVerse(1, "In the beginning")])],
                )
            ],
        )

        restored = parse_zefania_xml(serialize_zefania(bible))

        self.assertEqual(restored.name, bible.name)
        self.assertEqual(restored.books, bible.books)

    def test_openlyrics_zip_imports_nested_xml_and_reports_failures(self) -> None:
        song = Song(
            id="song-1",
            title="Archived Song",
            verses=[Verse("v1", "First line\nSecond line")],
            verse_order=["v1"],
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "openlyrics.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("songs/valid.xml", serialize_openlyrics(song))
                archive.writestr("songs/invalid.xml", "not XML")
                archive.writestr("readme.txt", "ignored")

            restored, failures = parse_openlyrics_archive(archive_path)

        self.assertEqual(restored[0].title, song.title)
        self.assertEqual(restored[0].verses, song.verses)
        self.assertEqual(failures, 1)

    def test_openlyrics_zip_supports_quelea_and_line_element_lyrics(self) -> None:
        quelea_xml = """<song xmlns="http://openlyrics.info/namespace/2009/song" version="0.9">
            <properties><titles><title>Quelea OpenLyrics</title></titles></properties>
            <lyrics><verse name="v1"><lines>First line<br/>Second line<br/></lines></verse></lyrics>
        </song>"""
        line_xml = """<song xmlns="http://openlyrics.info/namespace/2009/song" version="0.9">
            <properties><titles><title>Line Elements</title></titles></properties>
            <lyrics><verse name="v1"><lines><line>Alpha</line><line>Beta</line></lines></verse></lyrics>
        </song>"""
        empty_xml = """<song xmlns="http://openlyrics.info/namespace/2009/song" version="0.9">
            <properties><titles><title>Empty</title></titles></properties><lyrics/>
        </song>"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "quelea-openlyrics.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("quelea.xml", quelea_xml)
                archive.writestr("lines.xml", line_xml)
                archive.writestr("empty.xml", empty_xml)

            songs, failures = parse_openlyrics_archive(archive_path)

        self.assertEqual([song.title for song in songs], ["Quelea OpenLyrics", "Line Elements"])
        self.assertEqual(songs[0].verses, [Verse("v1", "First line\nSecond line")])
        self.assertEqual(songs[1].verses, [Verse("v1", "Alpha\nBeta")])
        self.assertEqual(failures, 1)

    def test_quelea_qsp_imports_native_song_xml(self) -> None:
        xml = """<song>
            <title>Quelea Song</title><author>Writer</author><ccli>123</ccli>
            <copyright>Copyright</copyright><key>G</key><capo>2</capo>
            <sequence>V1 C1</sequence><lyrics>
              <section title="Verse 1"><lyrics>Line one\nLine two\n</lyrics></section>
              <section title="Chorus 1"><lyrics>Chorus line\n</lyrics></section>
            </lyrics>
        </song>"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "songs.qsp"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("Quelea Song.xml", xml)

            songs, failures = parse_quelea_song_pack(archive_path)

        self.assertEqual(songs[0].title, "Quelea Song")
        self.assertEqual(
            songs[0].verses,
            [Verse("v1", "Line one\nLine two"), Verse("c1", "Chorus line")],
        )
        self.assertEqual(songs[0].verse_order, ["v1", "c1"])
        self.assertEqual(failures, 0)

    def test_quelea_qsp_supports_nested_lines_and_rejects_title_only_songs(self) -> None:
        nested_xml = """<song><title>Nested Lines</title><lyrics>
            <section title="Verse 1"><lyrics><line>Alpha</line><line>Beta</line></lyrics></section>
        </lyrics></song>"""
        empty_xml = """<song><title>Empty Song</title><lyrics>
            <section title="Verse 1"><lyrics/></section>
        </lyrics></song>"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "songs.qsp"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("nested.xml", nested_xml)
                archive.writestr("empty.xml", empty_xml)

            songs, failures = parse_quelea_song_pack(archive_path)

        self.assertEqual(songs[0].verses, [Verse("v1", "Alpha\nBeta")])
        self.assertEqual(failures, 1)


class LibraryPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self._root = Path(self._temp.name)
        self._original_songs_dir = song_repo.SONGS_DIR
        self._original_bibles_dir = bible_repo.BIBLES_DIR
        song_repo.SONGS_DIR = self._root / "source-songs"
        bible_repo.BIBLES_DIR = self._root / "source-bibles"
        song_repo._initialized_paths.clear()
        bible_repo._initialized_paths.clear()

    def tearDown(self) -> None:
        song_repo.SONGS_DIR = self._original_songs_dir
        bible_repo.BIBLES_DIR = self._original_bibles_dir
        song_repo._initialized_paths.clear()
        bible_repo._initialized_paths.clear()
        self._temp.cleanup()

    def test_package_round_trip_preserves_jdp_metadata(self) -> None:
        song = Song(
            id="song-1",
            title="Packaged Song",
            author="Author",
            capo="2",
            verses=[Verse("v1", "Line one\nLine two")],
            verse_order=["v1"],
            created_at="2026-09-05T10:00:00+00:00",
            updated_at="2026-09-05T11:00:00+00:00",
        )
        bible = BibleTranslation(
            id="bible-1",
            name="Packaged Bible",
            abbreviation="PKG",
            language="en",
            books=[BibleBook(1, "Genesis", [BibleChapter(1, [BibleVerse(1, "Text")])])],
        )
        song_repo.save_song(song)
        bible_repo.save_bible(bible)
        package = self._root / "library.jdplibrary"

        exported = export_library(package)
        song_repo.SONGS_DIR = self._root / "restored-songs"
        bible_repo.BIBLES_DIR = self._root / "restored-bibles"
        song_repo._initialized_paths.clear()
        bible_repo._initialized_paths.clear()
        imported = import_library(package)

        self.assertEqual(imported, exported)
        self.assertEqual(song_repo.load_song(song.id), song)
        self.assertEqual(bible_repo.load_bible_by_id(bible.id), bible)

    def test_service_can_be_restored_from_an_explicit_path(self) -> None:
        service = Service(
            id="service-1",
            version="1.0",
            name="Remembered Service",
            date="2026-09-06",
            theme=default_theme(),
        )
        path = self._root / "outside-default-folder" / "remembered.json"

        service_repo.save_service_to_path(service, str(path))

        self.assertEqual(service_repo.load_service_from_path(path), service)

    def test_convert_legacy_library_retains_source_files(self) -> None:
        song = Song(id="legacy-song", title="Legacy Song", verses=[Verse("v1", "Old lyrics")])
        bible = BibleTranslation(
            id="legacy-bible",
            name="Legacy Bible",
            abbreviation="LEG",
            language="en",
            books=[BibleBook(1, "Genesis", [BibleChapter(1, [BibleVerse(1, "Old text")])])],
        )
        self._write_legacy_library(song, bible)

        state = detect_legacy_library()
        summary = convert_legacy_library()

        self.assertEqual((state.songs, state.bibles), (1, 1))
        self.assertEqual((summary.songs, summary.bibles), (1, 1))
        self.assertEqual(song_repo.load_song(song.id), song)
        self.assertEqual(bible_repo.load_bible_by_id(bible.id), bible)
        self.assertTrue((Path(song_repo.SONGS_DIR) / f"{song.id}.json").exists())
        self.assertTrue((Path(bible_repo.BIBLES_DIR) / "index.json").exists())

    def test_replace_with_starter_retains_legacy_files_and_settings(self) -> None:
        packaged_song = Song(id="packaged-song", title="Packaged Song", verses=[Verse("v1", "New")])
        packaged_bible = BibleTranslation(
            id="packaged-bible",
            name="Packaged Bible",
            abbreviation="PKG",
            language="en",
            books=[BibleBook(1, "Genesis", [BibleChapter(1, [BibleVerse(1, "New text")])])],
        )
        song_repo.save_song(packaged_song)
        bible_repo.save_bible(packaged_bible)
        package = self._root / "starter.jdplibrary"
        export_library(package)

        song_repo.SONGS_DIR = self._root / "legacy-songs"
        bible_repo.BIBLES_DIR = self._root / "legacy-bibles"
        song_repo._initialized_paths.clear()
        bible_repo._initialized_paths.clear()
        legacy_song = Song(id="legacy-song", title="Legacy Song")
        legacy_bible = BibleTranslation(
            id="legacy-bible",
            name="Legacy Bible",
            abbreviation="LEG",
            language="en",
        )
        self._write_legacy_library(legacy_song, legacy_bible)
        settings = self._root / "settings.json"
        settings.write_text('{"rememberWindowState": true}', encoding="utf-8")

        summary = replace_with_starter_library(package)

        self.assertEqual((summary.songs, summary.bibles), (1, 1))
        self.assertEqual(song_repo.list_song_ids(), [packaged_song.id])
        self.assertEqual([entry.id for entry in bible_repo.list_bible_index()], [packaged_bible.id])
        self.assertTrue((Path(song_repo.SONGS_DIR) / f"{legacy_song.id}.json").exists())
        self.assertTrue((Path(bible_repo.BIBLES_DIR) / "index.json").exists())
        self.assertEqual(settings.read_text(encoding="utf-8"), '{"rememberWindowState": true}')

    @staticmethod
    def _write_legacy_library(song: Song, bible: BibleTranslation) -> None:
        songs_directory = Path(song_repo.SONGS_DIR)
        bibles_directory = Path(bible_repo.BIBLES_DIR)
        songs_directory.mkdir(parents=True, exist_ok=True)
        bibles_directory.mkdir(parents=True, exist_ok=True)
        (songs_directory / f"{song.id}.json").write_text(
            json.dumps(song.to_json_dict()), encoding="utf-8"
        )
        file_name = f"{bible.abbreviation.lower()}_{bible.id}.json"
        (bibles_directory / file_name).write_text(
            json.dumps(bible.to_json_dict()), encoding="utf-8"
        )
        (bibles_directory / "index.json").write_text(
            json.dumps(
                [
                    {
                        "id": bible.id,
                        "name": bible.name,
                        "abbreviation": bible.abbreviation,
                        "language": bible.language,
                        "fileName": file_name,
                    }
                ]
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
