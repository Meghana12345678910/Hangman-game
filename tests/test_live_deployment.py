"""Opt-in HTTPS deployment checks; never run against a host by default.

Set HANGMAN_DEPLOYMENT_URL to the service you own before running this module.
These checks create temporary in-memory games on that service.
"""

from collections import Counter
import os
from pathlib import Path
import time
import unittest
from urllib.parse import urlparse

try:
    from playwright.sync_api import sync_playwright, expect
except ImportError:
    sync_playwright = None


BASE = os.environ.get("HANGMAN_DEPLOYMENT_URL", "").rstrip("/")
ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(BASE and sync_playwright, "Set HANGMAN_DEPLOYMENT_URL and install requirements-dev.txt")
class LiveDeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if urlparse(BASE).scheme != "https":
            raise ValueError("Live deployment checks require HTTPS.")
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch(channel="chrome", headless=True)
        cls.addClassCleanup(cls.browser.close)
        cls.context = cls.browser.new_context(base_url=BASE)
        cls.addClassCleanup(cls.context.close)
        cls.api = cls.context.request
        cls.words = {
            difficulty: (ROOT / "words" / f"{difficulty}.txt").read_text().splitlines()
            for difficulty in ("easy", "medium", "hard")
        }

    def state(self, response, status=200):
        self.assertEqual(response.status, status)
        self.assertIn("application/json", response.headers.get("content-type", ""))
        state = response.json()
        expected = {"game_id", "pattern", "guessed_letters", "incorrect_letters", "remaining_guesses", "status"}
        if state["status"] != "playing":
            expected.add("word")
        self.assertEqual(set(state), expected)
        self.assertEqual(state["remaining_guesses"], 6 - len(state["incorrect_letters"]))
        return state

    def candidate_letter(self, difficulty, state):
        # Test data comes from the public word fixtures, never hidden fields.
        pattern = state["pattern"].split()
        guessed = set(state["guessed_letters"])
        candidates = [word for word in self.words[difficulty]
                      if len(word) == len(pattern)
                      and all((letter if letter in guessed else "_") == slot
                              for letter, slot in zip(word, pattern))]
        self.assertTrue(candidates, "Live word does not match the packaged word fixtures")
        counts = Counter(letter for word in candidates for letter in set(word) - guessed)
        return counts.most_common(1)[0][0]

    def test_01_health_and_deployed_assets(self):
        started = time.monotonic()
        response = self.api.get(BASE + "/", timeout=120000)
        self.assertEqual(response.status, 200)
        self.assertIn('id="keyboard"', response.text())
        print(f"\nInitial HTTPS response: {time.monotonic() - started:.2f}s (not an idle cold-start test)")
        for url, filename in (("/", "index.html"), ("/static/app.js", "app.js"), ("/static/style.css", "style.css")):
            response = self.api.get(BASE + url)
            self.assertEqual(response.status, 200)
            local = (ROOT / "static" / filename).read_text(encoding="utf-8")
            self.assertEqual(response.text().replace("\r\n", "\n"), local.replace("\r\n", "\n"))
        self.assertEqual(self.api.get(BASE + "/words/easy.txt").status, 404)

    def test_02_api_all_difficulties_validation_and_wins(self):
        for difficulty in self.words:
            state = self.state(self.api.post(BASE + "/api/games", data={"difficulty": difficulty}), 201)
            path = BASE + "/api/games/" + state["game_id"]
            self.assertEqual(self.state(self.api.get(path)), state)
            for body in ({"letter": ""}, {"letter": "ee"}, {"letter": "1"}, {"letter": None}, {"letter": "e", "word": "injected"}):
                response = self.api.post(path + "/guess", data=body)
                self.assertEqual(response.status, 400)
                self.assertEqual(set(response.json()), {"error"})
                self.assertEqual(self.state(self.api.get(path)), state)
            while state["status"] == "playing":
                letter = self.candidate_letter(difficulty, state)
                before = state
                state = self.state(self.api.post(path + "/guess", data={"letter": letter.upper()}))
                self.assertEqual(state["guessed_letters"], before["guessed_letters"] + [letter])
                duplicate = self.api.post(path + "/guess", data={"letter": letter})
                self.assertEqual(duplicate.status, 400)
                self.assertEqual(self.state(self.api.get(path)), state)
            self.assertEqual(state["status"], "won")
            self.assertIn(state["word"], self.words[difficulty])
        for body in ({"difficulty": "invalid"}, {}, {"difficulty": "easy", "word": "injected"}):
            response = self.api.post(BASE + "/api/games", data=body)
            self.assertEqual(response.status, 400)
            self.assertEqual(set(response.json()), {"error"})
        response = self.api.post(BASE + "/api/games", data="{", headers={"Content-Type": "application/json"})
        self.assertEqual(response.status, 400)
        self.assertEqual(self.api.get(BASE + "/api/games/missing-live-verification").status, 404)

    def start_browser_game(self, page, difficulty):
        page.locator("#difficulty").select_option(difficulty)
        with page.expect_response(lambda r: r.url == BASE + "/api/games" and r.request.method == "POST") as result:
            page.locator("#new-game").click()
        state = self.state(result.value, 201)
        expect(page.locator(".game")).to_have_attribute("aria-busy", "false")
        expect(page.locator("#remaining")).to_have_text("6 lives remaining")
        expect(page.locator("#guessed")).to_have_text("None yet")
        expect(page.locator("#incorrect")).to_have_text("None yet")
        expect(page.locator("#answer")).to_be_hidden()
        self.assertEqual(page.locator("[data-part]:not([hidden])").count(), 0)
        return state

    def browser_guess(self, page, state, letter, physical):
        path = BASE + "/api/games/" + state["game_id"] + "/guess"
        with page.expect_response(lambda r: r.url == path and r.request.method == "POST") as result:
            if physical:
                page.keyboard.press(letter.upper())
            else:
                page.get_by_role("button", name=f"Guess {letter.upper()}", exact=True).click()
        updated = self.state(result.value)
        expect(page.locator(".game")).to_have_attribute("aria-busy", "false")
        expect(page.locator("#pattern")).to_have_text(updated["pattern"])
        self.assertEqual(page.locator("[data-part]:not([hidden])").count(), len(updated["incorrect_letters"]))
        expect(page.get_by_role("button", name=f"Guess {letter.upper()}", exact=True)).to_be_disabled()
        expect(page.locator("#error")).to_be_hidden()
        return updated

    def test_03_browser_play_and_responsive_layout(self):
        page = self.context.new_page()
        self.addCleanup(page.close)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(BASE, timeout=120000)
        for difficulty, width in (("easy", 1280), ("medium", 390), ("hard", 320)):
            page.set_viewport_size({"width": width, "height": 900})
            state = self.start_browser_game(page, difficulty)
            turn = 0
            while state["status"] == "playing":
                letter = self.candidate_letter(difficulty, state)
                before = state
                state = self.browser_guess(page, state, letter, turn % 2 == 0)
                if letter not in state["incorrect_letters"]:
                    self.assertEqual(before["remaining_guesses"], state["remaining_guesses"])
                turn += 1
            self.assertEqual(state["status"], "won")
            expect(page.locator("#message")).to_contain_text("You found it!")
            expect(page.locator("#answer")).to_have_text(f"The word was {state['word'].upper()}.")
            self.assertEqual(page.locator(".letter:disabled").count(), 26)
            self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            for selector in ("#new-game", "#difficulty", ".letter"):
                self.assertGreaterEqual(page.locator(selector).first.bounding_box()["height"], 44)
        state = self.start_browser_game(page, "easy")
        for index, letter in enumerate("zqxjkd"):
            state = self.browser_guess(page, state, letter, index % 2 == 0)
            self.assertEqual(state["remaining_guesses"], 5 - index)
        self.assertEqual(state["status"], "lost")
        expect(page.locator("#message")).to_contain_text("Out of lives")
        expect(page.locator("#answer")).to_be_visible()
        self.assertEqual(page.locator(".letter:disabled").count(), 26)
        self.start_browser_game(page, "easy")
        self.assertEqual(errors, [])
