"""Behavior tests for the standalone game engine."""

import json
import unittest

from game import HangmanGame, InvalidGuessError


class HangmanGameTests(unittest.TestCase):
    def test_initial_state_is_safe_and_json_serializable(self):
        state = HangmanGame("eagle").to_state()
        self.assertEqual(state, {
            "pattern": "_ _ _ _ _",
            "guessed_letters": [],
            "incorrect_letters": [],
            "remaining_guesses": 6,
            "status": "playing",
        })
        self.assertNotIn("eagle", json.dumps(state))

    def test_case_normalization_reveals_all_occurrences_without_cost(self):
        state = HangmanGame("EaGlE").guess("E")
        self.assertEqual(state["pattern"], "e _ _ _ e")
        self.assertEqual(state["guessed_letters"], ["e"])
        self.assertEqual(state["incorrect_letters"], [])
        self.assertEqual(state["remaining_guesses"], 6)
        self.assertNotIn("word", state)

    def test_incorrect_guess_costs_one_life(self):
        state = HangmanGame("eagle").guess("Z")
        self.assertEqual(state["incorrect_letters"], ["z"])
        self.assertEqual(state["guessed_letters"], ["z"])
        self.assertEqual(state["remaining_guesses"], 5)
        self.assertEqual(state["pattern"], "_ _ _ _ _")
        self.assertEqual(state["status"], "playing")

    def test_invalid_guesses_leave_state_unchanged(self):
        game = HangmanGame("eagle")
        for letter in ("", "ee", "1", "!", " ", " e", "e ", "é", "İ", None, 1, [], {}):
            with self.subTest(letter=letter):
                before = game.to_state()
                with self.assertRaises(InvalidGuessError):
                    game.guess(letter)
                self.assertEqual(game.to_state(), before)

    def test_correct_and_incorrect_duplicates_are_case_insensitive(self):
        for letter in ("e", "z"):
            with self.subTest(letter=letter):
                game = HangmanGame("eagle")
                game.guess(letter)
                before = game.to_state()
                with self.assertRaises(InvalidGuessError):
                    game.guess(letter.upper())
                self.assertEqual(game.to_state(), before)

    def test_win_reveals_answer_only_on_final_letter(self):
        game = HangmanGame("eagle")
        for letter in "eag":
            state = game.guess(letter)
            self.assertEqual(state["status"], "playing")
            self.assertNotIn("word", state)
        state = game.guess("l")
        self.assertEqual(state["status"], "won")
        self.assertEqual(state["word"], "eagle")
        self.assertEqual(state["pattern"], "e a g l e")
        self.assertEqual(state["remaining_guesses"], 6)

    def test_sixth_miss_loses_and_reveals_answer(self):
        game = HangmanGame("eagle")
        for remaining, letter in zip(range(5, -1, -1), "zxcvbn"):
            state = game.guess(letter)
            self.assertEqual(state["remaining_guesses"], remaining)
            if remaining:
                self.assertEqual(state["status"], "playing")
                self.assertNotIn("word", state)
        self.assertEqual(state["status"], "lost")
        self.assertEqual(state["word"], "eagle")

    def test_can_win_with_one_life_remaining(self):
        game = HangmanGame("a")
        for letter in "zxcvb":
            game.guess(letter)
        state = game.guess("A")
        self.assertEqual(state["status"], "won")
        self.assertEqual(state["remaining_guesses"], 1)

    def test_post_game_guesses_leave_win_and_loss_unchanged(self):
        for guesses in ("a", "zxcvbn"):
            game = HangmanGame("a")
            for letter in guesses:
                game.guess(letter)
            before = game.to_state()
            for letter in ("a", "q", ""):
                with self.assertRaises(InvalidGuessError):
                    game.guess(letter)
                self.assertEqual(game.to_state(), before)

    def test_snapshots_cannot_mutate_game_or_previous_snapshots(self):
        game = HangmanGame("eagle")
        old = game.to_state()
        state = game.guess("z")
        state["guessed_letters"].append("e")
        state["incorrect_letters"].clear()
        state["status"] = "won"
        self.assertEqual(old["guessed_letters"], [])
        self.assertEqual(game.to_state()["guessed_letters"], ["z"])
        self.assertEqual(game.to_state()["incorrect_letters"], ["z"])
        self.assertEqual(game.to_state()["status"], "playing")

    def test_games_are_independent(self):
        first, second = HangmanGame("a"), HangmanGame("a")
        first.guess("a")
        self.assertEqual(second.to_state()["status"], "playing")
        self.assertEqual(second.to_state()["guessed_letters"], [])

    def test_invalid_words_fail_at_construction(self):
        for word in ("", "two words", "a-b", "123", "café", None, 5):
            with self.subTest(word=word), self.assertRaises(ValueError):
                HangmanGame(word)


if __name__ == "__main__":
    unittest.main()
