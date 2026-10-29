"""Hangman rules and client-safe state, independent of any web framework."""

from string import ascii_lowercase


class InvalidGuessError(ValueError):
    """A guess cannot be applied to the current game."""


class HangmanGame:
    """Play a supplied word with six allowed incorrect guesses.

    Words and guesses use English A-Z letters and are normalized to lowercase.
    Word selection belongs to the word manager, not this class.
    """

    def __init__(self, word: str):
        if not isinstance(word, str) or not word or any(
            letter not in ascii_lowercase for letter in word.lower()
        ):
            raise ValueError("Word must contain only A-Z letters and cannot be empty.")
        self._word = word.lower()
        self._guessed_letters: list[str] = []
        self._incorrect_letters: list[str] = []

    def guess(self, letter: str) -> dict:
        """Apply one new letter and return state; rejected guesses change nothing."""
        if self._status() != "playing":
            raise InvalidGuessError("The game has already ended.")
        if (
            not isinstance(letter, str)
            or len(letter) != 1
            or letter.lower() not in ascii_lowercase
        ):
            raise InvalidGuessError("Guess must be one A-Z letter.")
        letter = letter.lower()
        if letter in self._guessed_letters:
            raise InvalidGuessError("That letter has already been guessed.")

        self._guessed_letters.append(letter)
        if letter not in self._word:
            self._incorrect_letters.append(letter)
        return self.to_state()

    def _status(self) -> str:
        if all(letter in self._guessed_letters for letter in self._word):
            return "won"
        if len(self._incorrect_letters) == 6:
            return "lost"
        return "playing"

    def to_state(self) -> dict:
        """Return a fresh public snapshot, revealing the word only at game end."""
        status = self._status()
        state = {
            "pattern": " ".join(
                letter if letter in self._guessed_letters else "_"
                for letter in self._word
            ),
            "guessed_letters": self._guessed_letters.copy(),
            "incorrect_letters": self._incorrect_letters.copy(),
            "remaining_guesses": 6 - len(self._incorrect_letters),
            "status": status,
        }
        if status != "playing":
            state["word"] = self._word
        return state
