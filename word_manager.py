"""Load validated word lists and select words without depending on Flask."""

from pathlib import Path
import random
from string import ascii_lowercase


class InvalidDifficultyError(ValueError):
    """The requested difficulty is not supported."""


class WordListError(ValueError):
    """A required word list cannot be loaded or contains invalid data."""


class WordManager:
    """Load all three lists at startup; fail clearly rather than use bad data."""

    DIFFICULTIES = ("easy", "medium", "hard")

    def __init__(self, words_dir: str | Path | None = None):
        directory = (
            Path(words_dir) if words_dir is not None
            else Path(__file__).resolve().parent / "words"
        )
        self._words: dict[str, tuple[str, ...]] = {}
        for difficulty in self.DIFFICULTIES:
            path = directory / f"{difficulty}.txt"
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                raise WordListError(f"Cannot read word list {path}: {error}") from error

            words = dict.fromkeys(
                line.strip().lower() for line in content.splitlines() if line.strip()
            )
            for number, line in enumerate(content.splitlines(), start=1):
                word = line.strip().lower()
                if word and any(letter not in ascii_lowercase for letter in word):
                    raise WordListError(
                        f"Invalid entry in {path} at line {number}: use only A-Z letters."
                    )
            if not words:
                raise WordListError(f"Word list {path} is empty.")
            self._words[difficulty] = tuple(words)

    def random_word(self, difficulty: str) -> str:
        """Choose uniformly among the unique words for a difficulty."""
        if not isinstance(difficulty, str) or difficulty not in self._words:
            raise InvalidDifficultyError("Difficulty must be easy, medium, or hard.")
        return random.choice(self._words[difficulty])
