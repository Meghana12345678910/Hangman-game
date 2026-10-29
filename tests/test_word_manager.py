"""Word-loading tests use temporary files and deterministic random choices."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from game import HangmanGame
from word_manager import InvalidDifficultyError, WordListError, WordManager


class WordManagerTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        for difficulty, content in {
            "easy": " Apple \n\nAPPLE\napple\n beach \n",
            "medium": "Lantern\ncompass\n",
            "hard": "xylophone\nlabyrinth\n",
        }.items():
            self.write(difficulty, content)

    def write(self, difficulty, content):
        (self.directory / f"{difficulty}.txt").write_text(content, encoding="utf-8")

    def test_normalizes_skips_blanks_and_deduplicates_before_selection(self):
        manager = WordManager(self.directory)
        with patch("word_manager.random.choice", return_value="beach") as choose:
            self.assertEqual(manager.random_word("easy"), "beach")
            choose.assert_called_once_with(("apple", "beach"))

    def test_each_difficulty_uses_its_own_list(self):
        manager = WordManager(self.directory)
        for difficulty, expected in {
            "easy": ("apple", "beach"),
            "medium": ("lantern", "compass"),
            "hard": ("xylophone", "labyrinth"),
        }.items():
            with self.subTest(difficulty=difficulty):
                with patch("word_manager.random.choice", side_effect=lambda words: words[-1]) as choose:
                    self.assertEqual(manager.random_word(difficulty), expected[-1])
                    choose.assert_called_once_with(expected)

    def test_invalid_difficulties_raise_clear_error(self):
        manager = WordManager(self.directory)
        for difficulty in ("expert", "Easy", "", " easy ", None, 1, [], {}):
            with self.subTest(difficulty=difficulty):
                with self.assertRaisesRegex(InvalidDifficultyError, "easy, medium, or hard"):
                    manager.random_word(difficulty)

    def test_missing_list_identifies_file(self):
        (self.directory / "medium.txt").unlink()
        with self.assertRaisesRegex(WordListError, r"Cannot read word list .*medium\.txt"):
            WordManager(self.directory)

    def test_missing_directory_raises_word_list_error(self):
        with self.assertRaisesRegex(WordListError, "Cannot read word list"):
            WordManager(self.directory / "missing")

    def test_empty_and_blank_only_lists_are_rejected(self):
        for content in ("", " \n\t\n"):
            with self.subTest(content=content):
                self.write("hard", content)
                with self.assertRaisesRegex(WordListError, r"hard\.txt is empty"):
                    WordManager(self.directory)

    def test_invalid_entries_identify_file_and_line(self):
        for entry in ("two words", "apple-pie", "123", "café", "hello!", "İ"):
            with self.subTest(entry=entry):
                self.write("easy", f"apple\n{entry}\n")
                with self.assertRaisesRegex(WordListError, r"easy\.txt at line 2"):
                    WordManager(self.directory)

    def test_invalid_utf8_raises_word_list_error(self):
        (self.directory / "easy.txt").write_bytes(b"\xff")
        with self.assertRaisesRegex(WordListError, r"Cannot read word list .*easy\.txt"):
            WordManager(self.directory)

    def test_single_unique_word_is_selectable(self):
        self.write("easy", "APPLE\napple\n")
        self.assertEqual(WordManager(self.directory).random_word("easy"), "apple")

    def test_shipped_lists_work_outside_project_directory_and_with_engine(self):
        # A changed cwd must not affect the module-relative default word path.
        import os

        previous = Path.cwd()
        try:
            os.chdir(self.directory)
            manager = WordManager()
        finally:
            os.chdir(previous)
        shipped = Path(__file__).resolve().parent.parent / "words"
        for difficulty in WordManager.DIFFICULTIES:
            expected = (shipped / f"{difficulty}.txt").read_text().splitlines()
            for word in expected:
                self.assertEqual(HangmanGame(word).to_state()["status"], "playing")
            self.assertIn(manager.random_word(difficulty), expected)


if __name__ == "__main__":
    unittest.main()
