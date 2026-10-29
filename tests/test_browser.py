"""Browser behavior and integration regressions against Flask in Google Chrome.

Install requirements-dev.txt to run these tests. Backend-only environments can
still run the rest of the suite without Playwright.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from werkzeug.serving import make_server

from server import create_app
from word_manager import WordManager

try:
    from playwright.sync_api import sync_playwright, expect
except ImportError:
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, "Install requirements-dev.txt for browser tests")
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        for difficulty, word in {"easy": "eagle", "medium": "compass", "hard": "xylophone"}.items():
            (directory / f"{difficulty}.txt").write_text(word, encoding="utf-8")
        cls.server = make_server("127.0.0.1", 0, create_app(WordManager(directory)), threaded=True)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.stop_server)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch(channel="chrome", headless=True)
        cls.addClassCleanup(cls.browser.close)

    @classmethod
    def stop_server(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1280, "height": 900})
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(self.url)

    def tearDown(self):
        self.assertEqual(self.errors, [])

    def start(self, difficulty="easy"):
        self.page.locator("#difficulty").select_option(difficulty)
        self.page.get_by_role("button", name="New Game").click()
        expect(self.page.locator("#remaining")).to_have_text("6 lives remaining")
        expect(self.page.get_by_role("button", name="Guess A", exact=True)).to_be_enabled()

    def test_initial_page_and_keyboard_disabled_until_start(self):
        expect(self.page).to_have_title("Hangman — One letter at a time")
        self.assertEqual(self.page.locator(".letter").count(), 26)
        self.assertEqual(self.page.locator(".letter:disabled").count(), 26)
        expect(self.page.locator("#answer")).to_be_hidden()
        self.start()
        expect(self.page.locator("#pattern")).to_have_text("_ _ _ _ _")
        expect(self.page.locator("#guessed")).to_have_text("None yet")

    def test_physical_keyboard_win_and_no_active_answer_in_responses(self):
        active_responses = []
        def inspect(response):
            if "/api/games" in response.url and response.ok:
                data = response.json()
                if data["status"] == "playing":
                    active_responses.append(data)
        self.page.on("response", inspect)
        self.start()
        for letter in "Eagl":
            self.page.keyboard.press(letter)
            expect(self.page.get_by_role("button", name=f"Guess {letter.upper()}", exact=True)).to_be_disabled()
            expect(self.page.locator(".game")).to_have_attribute("aria-busy", "false")
        expect(self.page.locator("#message")).to_contain_text("You found it!")
        expect(self.page.locator("#answer")).to_have_text("The word was EAGLE.")
        self.assertEqual(self.page.locator(".letter:disabled").count(), 26)
        self.assertGreater(len(active_responses), 0)
        for data in active_responses:
            self.assertNotIn("word", data)
            self.assertNotIn("eagle", str(data))
        self.start()
        expect(self.page.locator("#answer")).to_be_hidden()
        expect(self.page.locator("#guessed")).to_have_text("None yet")

    def test_on_screen_keyboard_loss_drawing_and_restart(self):
        self.start()
        for index, letter in enumerate("ZXCVBN", start=1):
            self.page.get_by_role("button", name=f"Guess {letter}", exact=True).click()
            expect(self.page.locator("#remaining")).to_have_text(f"{6-index} {'life' if index == 5 else 'lives'} remaining")
            self.assertEqual(self.page.locator("[data-part]:not([hidden])").count(), index)
        expect(self.page.locator("#message")).to_contain_text("Out of lives")
        expect(self.page.locator("#answer")).to_have_text("The word was EAGLE.")
        expect(self.page.locator("#incorrect")).to_have_text("Z X C V B N")
        self.assertEqual(self.page.locator(".letter:disabled").count(), 26)
        self.start()
        self.assertEqual(self.page.locator("[data-part]:not([hidden])").count(), 0)

    def test_each_difficulty_and_responsive_layout(self):
        for width in (1280, 390, 320):
            self.page.set_viewport_size({"width": width, "height": 900})
            for difficulty, length in (("easy", 5), ("medium", 7), ("hard", 9)):
                with self.subTest(width=width, difficulty=difficulty):
                    self.start(difficulty)
                    expect(self.page.locator("#pattern")).to_have_text(" ".join("_" * length))
                    self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
                    for selector in ("#new-game", "#difficulty", ".letter"):
                        box = self.page.locator(selector).first.bounding_box()
                        self.assertGreaterEqual(box["height"], 44)
        # Also check a long final answer at the narrowest width.
        for letter in "xylophone":
            if not self.page.get_by_role("button", name=f"Guess {letter.upper()}", exact=True).is_disabled():
                self.page.get_by_role("button", name=f"Guess {letter.upper()}", exact=True).click()
                expect(self.page.locator(".game")).to_have_attribute("aria-busy", "false")
        expect(self.page.locator("#answer")).to_be_visible()
        self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= innerWidth"))

    def test_loading_disables_controls_and_failure_allows_retry(self):
        held = []
        self.page.route("**/api/games", lambda route: held.append(route))
        self.page.get_by_role("button", name="New Game").click()
        expect(self.page.locator("#message")).to_have_text("Finding a new word…")
        expect(self.page.locator("#new-game")).to_be_disabled()
        expect(self.page.locator("#difficulty")).to_be_disabled()
        expect(self.page.locator(".game")).to_have_attribute("aria-busy", "true")
        self.assertEqual(len(held), 1)
        held[0].fulfill(status=503, content_type="application/json", body='{"error":"Temporarily unavailable"}')
        expect(self.page.locator("#error")).to_have_text("Temporarily unavailable")
        expect(self.page.locator("#new-game")).to_be_enabled()
        self.page.unroute("**/api/games")
        self.start()
        expect(self.page.locator("#error")).to_be_hidden()

    def test_correct_guess_drawing_and_guess_error_feedback(self):
        self.start()
        self.page.get_by_role("button", name="Guess E", exact=True).click()
        expect(self.page.locator("#pattern")).to_have_text("e _ _ _ e")
        self.assertEqual(self.page.locator("[data-part]:not([hidden])").count(), 0)
        self.page.route("**/guess", lambda route: route.fulfill(status=400, content_type="application/json", body='{"error":"Guess rejected"}'))
        self.page.get_by_role("button", name="Guess A", exact=True).click()
        expect(self.page.locator("#error")).to_have_text("Guess rejected")
        expect(self.page.get_by_role("button", name="Guess A", exact=True)).to_be_enabled()
        expect(self.page.locator("#pattern")).to_have_text("e _ _ _ e")

    def test_accepted_guess_with_lost_response_refreshes_server_state(self):
        self.start()
        def lose_response(route):
            response = route.fetch()
            self.assertEqual(response.status, 200)
            route.abort("failed")
        self.page.route("**/guess", lose_response)
        self.page.get_by_role("button", name="Guess Z", exact=True).click()
        expect(self.page.locator("#error")).to_be_visible()
        expect(self.page.locator("#remaining")).to_have_text("5 lives remaining")
        expect(self.page.locator("#incorrect")).to_have_text("Z")
        expect(self.page.get_by_role("button", name="Guess Z", exact=True)).to_be_disabled()
        self.assertEqual(self.page.locator("[data-part]:not([hidden])").count(), 1)

    def test_offline_guess_blocks_stale_game_until_new_game(self):
        self.start()
        self.context.set_offline(True)
        self.page.get_by_role("button", name="Guess Z", exact=True).click()
        expect(self.page.locator("#error")).to_be_visible()
        expect(self.page.locator(".game")).to_have_attribute("aria-busy", "false")
        expect(self.page.locator("#message")).to_contain_text("Could not refresh")
        self.assertEqual(self.page.locator(".letter:disabled").count(), 26)
        expect(self.page.locator("#new-game")).to_be_enabled()
        self.context.set_offline(False)
        self.start()
        expect(self.page.locator("#error")).to_be_hidden()
        expect(self.page.locator("#guessed")).to_have_text("None yet")

    def test_rapid_clicks_and_invalid_repeated_keys_send_one_guess(self):
        self.start()
        held = []
        self.page.route("**/guess", lambda route: held.append(route))
        self.page.evaluate("""() => {
            document.querySelector('[data-letter=z]').click();
            document.querySelector('[data-letter=x]').click();
            document.querySelector('#new-game').click();
        }""")
        expect(self.page.locator(".game")).to_have_attribute("aria-busy", "true")
        self.page.keyboard.press("a")
        self.assertEqual(len(held), 1)
        held[0].continue_()
        expect(self.page.locator("#incorrect")).to_have_text("Z")
        self.page.unroute("**/guess")
        sent = []
        self.page.on("request", lambda request: sent.append(request.url) if request.url.endswith("/guess") else None)
        for key in ("z", "Z", "1", "!", "Control+a"):
            self.page.keyboard.press(key)
        self.page.evaluate("document.dispatchEvent(new KeyboardEvent('keydown', {key:'a', repeat:true}))")
        # A real new guess is the barrier: earlier key events must send nothing.
        self.page.get_by_role("button", name="Guess E", exact=True).click()
        expect(self.page.locator("#guessed")).to_have_text("Z E")
        self.assertEqual(len(sent), 1)
        expect(self.page.locator("#remaining")).to_have_text("5 lives remaining")

    def test_two_browser_games_stay_independent(self):
        self.start()
        other = self.context.new_page()
        other.goto(self.url)
        other.locator("#new-game").click()
        expect(other.locator("#remaining")).to_have_text("6 lives remaining")
        self.page.get_by_role("button", name="Guess Z", exact=True).click()
        expect(self.page.locator("#remaining")).to_have_text("5 lives remaining")
        expect(other.locator("#guessed")).to_have_text("None yet")
        other.get_by_role("button", name="Guess E", exact=True).click()
        expect(other.locator("#pattern")).to_have_text("e _ _ _ e")
        expect(other.locator("#remaining")).to_have_text("6 lives remaining")
        expect(self.page.locator("#pattern")).to_have_text("_ _ _ _ _")

    def test_lost_final_response_shows_server_win(self):
        self.start()
        for letter in "eag":
            self.page.get_by_role("button", name=f"Guess {letter.upper()}", exact=True).click()
            expect(self.page.locator(".game")).to_have_attribute("aria-busy", "false")
        def lose_response(route):
            route.fetch()
            route.abort("failed")
        self.page.route("**/guess", lose_response)
        self.page.get_by_role("button", name="Guess L", exact=True).click()
        expect(self.page.locator("#message")).to_contain_text("You found it!")
        expect(self.page.locator("#answer")).to_have_text("The word was EAGLE.")
        self.assertEqual(self.page.locator(".letter:disabled").count(), 26)
        self.start()

    def test_timeout_releases_controls(self):
        self.page.clock.install()
        held = []
        self.page.route("**/api/games", lambda route: held.append(route))
        self.page.locator("#new-game").click()
        expect(self.page.locator(".game")).to_have_attribute("aria-busy", "true")
        self.page.clock.fast_forward(16000)
        expect(self.page.locator("#error")).to_contain_text("timed out")
        expect(self.page.locator("#new-game")).to_be_enabled()
        expect(self.page.locator(".game")).to_have_attribute("aria-busy", "false")
        held[0].abort()
        self.page.unroute("**/api/games")
        self.start()
