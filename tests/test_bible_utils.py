from __future__ import annotations

import unittest

from app.utils.bible_utils import resolve_book_name


class BibleAbbreviationTests(unittest.TestCase):
    def test_standard_three_letter_abbreviations_cover_all_66_books(self) -> None:
        abbreviations = {
            "Gen": "Genesis",
            "Exo": "Exodus",
            "Lev": "Leviticus",
            "Num": "Numbers",
            "Deu": "Deuteronomy",
            "Jos": "Joshua",
            "Jdg": "Judges",
            "Rut": "Ruth",
            "1Sa": "1 Samuel",
            "2Sa": "2 Samuel",
            "1Ki": "1 Kings",
            "2Ki": "2 Kings",
            "1Ch": "1 Chronicles",
            "2Ch": "2 Chronicles",
            "Ezr": "Ezra",
            "Neh": "Nehemiah",
            "Est": "Esther",
            "Job": "Job",
            "Psa": "Psalms",
            "Pro": "Proverbs",
            "Ecc": "Ecclesiastes",
            "Sng": "Song of Songs",
            "Isa": "Isaiah",
            "Jer": "Jeremiah",
            "Lam": "Lamentations",
            "Eze": "Ezekiel",
            "Dan": "Daniel",
            "Hos": "Hosea",
            "Joe": "Joel",
            "Amo": "Amos",
            "Oba": "Obadiah",
            "Jon": "Jonah",
            "Mic": "Micah",
            "Nah": "Nahum",
            "Hab": "Habakkuk",
            "Zep": "Zephaniah",
            "Hag": "Haggai",
            "Zec": "Zechariah",
            "Mal": "Malachi",
            "Mat": "Matthew",
            "Mar": "Mark",
            "Luk": "Luke",
            "Joh": "John",
            "Act": "Acts",
            "Rom": "Romans",
            "1Co": "1 Corinthians",
            "2Co": "2 Corinthians",
            "Gal": "Galatians",
            "Eph": "Ephesians",
            "Php": "Philippians",
            "Col": "Colossians",
            "1Th": "1 Thessalonians",
            "2Th": "2 Thessalonians",
            "1Ti": "1 Timothy",
            "2Ti": "2 Timothy",
            "Tit": "Titus",
            "Phm": "Philemon",
            "Heb": "Hebrews",
            "Jas": "James",
            "1Pe": "1 Peter",
            "2Pe": "2 Peter",
            "1Jn": "1 John",
            "2Jn": "2 John",
            "3Jn": "3 John",
            "Jud": "Jude",
            "Rev": "Revelation",
        }

        self.assertEqual(len(abbreviations), 66)
        for abbreviation, expected_book in abbreviations.items():
            with self.subTest(abbreviation=abbreviation):
                self.assertEqual(resolve_book_name(abbreviation), expected_book)


if __name__ == "__main__":
    unittest.main()