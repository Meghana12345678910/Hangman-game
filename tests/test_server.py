"""API contracts and complete games with controlled word lists."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from server import create_app
from word_manager import WordManager


class ApiTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        for difficulty, word in {"easy": "eagle", "medium": "compass", "hard": "xylophone"}.items():
            (directory / f"{difficulty}.txt").write_text(word, encoding="utf-8")
        self.manager = WordManager(directory)
        self.app = create_app(self.manager)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def create(self, difficulty="easy"):
        response = self.client.post("/api/games", json={"difficulty": difficulty})
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def guess(self, game_id, letter):
        return self.client.post(f"/api/games/{game_id}/guess", json={"letter": letter})

    def assert_error(self, response, status=400):
        self.assertEqual(response.status_code, status)
        self.assertTrue(response.is_json)
        self.assertEqual(set(response.get_json()), {"error"})
        self.assertIsInstance(response.get_json()["error"], str)

    def test_creation_and_get_for_each_difficulty(self):
        for difficulty, length in (("easy", 5), ("medium", 7), ("hard", 9)):
            state = self.create(difficulty)
            self.assertEqual(set(state), {"game_id", "pattern", "guessed_letters", "incorrect_letters", "remaining_guesses", "status"})
            self.assertEqual(state["pattern"], " ".join("_" * length))
            self.assertEqual(state["remaining_guesses"], 6)
            self.assertEqual(state["status"], "playing")
            self.assertEqual(state["guessed_letters"], [])
            self.assertEqual(state["incorrect_letters"], [])
            response = self.client.get(f"/api/games/{state['game_id']}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json(), state)

    def test_complete_win_and_post_game_rejection(self):
        game_id = self.create()["game_id"]
        for letter in "Eag":
            response = self.guess(game_id, letter)
            self.assertEqual(response.status_code, 200)
            state = response.get_json()
            self.assertEqual(state["status"], "playing")
            self.assertNotIn("word", state)
            self.assertNotIn("eagle", response.get_data(as_text=True))
        state = self.guess(game_id, "l").get_json()
        self.assertEqual(state["status"], "won")
        self.assertEqual(state["word"], "eagle")
        self.assertEqual(state["pattern"], "e a g l e")
        self.assertEqual(state["remaining_guesses"], 6)
        self.assert_error(self.guess(game_id, "z"))
        self.assertEqual(self.client.get(f"/api/games/{game_id}").get_json(), state)

    def test_complete_loss_and_post_game_rejection(self):
        game_id = self.create()["game_id"]
        for remaining, letter in zip(range(5, -1, -1), "zxcvbn"):
            response = self.guess(game_id, letter)
            self.assertEqual(response.status_code, 200)
            state = response.get_json()
            self.assertEqual(state["remaining_guesses"], remaining)
            if remaining:
                self.assertNotIn("word", state)
        self.assertEqual(state["status"], "lost")
        self.assertEqual(state["word"], "eagle")
        self.assert_error(self.guess(game_id, "e"))
        self.assertEqual(self.client.get(f"/api/games/{game_id}").get_json(), state)

    def test_independent_games_and_app_instances(self):
        first, second = self.create(), self.create()
        self.assertNotEqual(first["game_id"], second["game_id"])
        self.guess(first["game_id"], "z")
        self.assertEqual(self.client.get(f"/api/games/{second['game_id']}").get_json(), second)
        other = create_app(self.manager).test_client()
        self.assert_error(other.get(f"/api/games/{first['game_id']}"), 404)

    def test_invalid_difficulties(self):
        for difficulty in (None, "", "expert", "Easy", [], {}, 1):
            with self.subTest(difficulty=difficulty):
                self.assert_error(self.client.post("/api/games", json={"difficulty": difficulty}))

    def test_invalid_and_duplicate_guesses_do_not_change_state(self):
        game_id = self.create()["game_id"]
        for accepted in ("e", "z"):
            before = self.guess(game_id, accepted).get_json()
            for letter in (accepted.upper(), "", "ee", "1", "é", None, [], {}, 1):
                with self.subTest(letter=letter):
                    self.assert_error(self.guess(game_id, letter))
                    self.assertEqual(self.client.get(f"/api/games/{game_id}").get_json(), before)

    def test_malformed_bodies_and_attempted_state_injection(self):
        state = self.create()
        game_id = state["game_id"]
        for url, field, value in (("/api/games", "difficulty", "easy"), (f"/api/games/{game_id}/guess", "letter", "e")):
            for body in ("{", "null", "[]", '"text"', "42", "{}", '{"wrong":"e"}'):
                with self.subTest(url=url, body=body):
                    self.assert_error(self.client.post(url, data=body, content_type="application/json"))
            for extra in ("word", "status", "remaining_guesses", "game_id", "pattern"):
                self.assert_error(self.client.post(url, json={field: value, extra: "injected"}))
            self.assert_error(self.client.post(url))
            self.assert_error(self.client.post(url, data="text", content_type="text/plain"))
        self.assertEqual(self.client.get(f"/api/games/{game_id}").get_json(), state)

    def test_unknown_ids_routes_and_methods_return_json(self):
        self.assert_error(self.client.get("/api/games/missing"), 404)
        self.assert_error(self.guess("missing", "e"), 404)
        self.assert_error(self.client.get("/api/unknown"), 404)
        response = self.client.delete("/api/games")
        self.assert_error(response, 405)
        self.assertIn("POST", response.headers["Allow"])

    def test_browser_page_and_assets_are_served_without_exposing_word_lists(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        self.assertIn(b'id="keyboard"', response.data)
        response.close()
        for path in ("/static/style.css", "/static/app.js"):
            with self.client.get(path) as asset:
                self.assertEqual(asset.status_code, 200)
        self.assert_error(self.client.get("/words/easy.txt"), 404)


if __name__ == "__main__":
    unittest.main()
