"""Exercise the real production server on a supplied port, with bundled assets."""

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import production


class ProductionTests(unittest.TestCase):
    def test_production_disables_debug_and_uses_one_thread(self):
        with patch.dict(os.environ, {"PORT": "12345", "FLASK_DEBUG": "1"}):
            with patch("production.serve") as serve:
                production.main()
        app = serve.call_args.args[0]
        self.assertFalse(app.debug)
        self.assertFalse(app.testing)
        self.assertEqual(serve.call_args.kwargs, {"host": "0.0.0.0", "port": 12345, "threads": 1})

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        root = Path(__file__).resolve().parent.parent
        for name in ("production.py", "server.py", "game.py", "word_manager.py"):
            shutil.copy2(root / name, self.directory / name)
        shutil.copytree(root / "static", self.directory / "static")
        (self.directory / "words").mkdir()
        for difficulty, word in {"easy": "eagle", "medium": "compass", "hard": "xylophone"}.items():
            (self.directory / "words" / f"{difficulty}.txt").write_text(word, encoding="utf-8")

    def start(self):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        self.base = f"http://127.0.0.1:{port}"
        self.log = open(self.directory / f"server-{port}.log", "w+", encoding="utf-8")
        self.addCleanup(self.log.close)
        self.process = subprocess.Popen(
            [sys.executable, str(self.directory / "production.py")],
            cwd=self.directory,
            env={**os.environ, "PORT": str(port), "FLASK_DEBUG": "1"},
            stdout=self.log, stderr=subprocess.STDOUT,
        )
        self.addCleanup(self.stop, self.process)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail("Production process exited before becoming ready.")
            try:
                with urlopen(self.base, timeout=1) as response:
                    if response.status == 200:
                        return
            except (URLError, TimeoutError):
                time.sleep(.05)
        self.fail("Production server did not bind the supplied PORT.")

    @staticmethod
    def stop(process):
        if process.poll() is None:
            if os.name == "nt":
                # Windows virtualenv launchers can have a Python child. Stop
                # only this test-owned tree so it cannot retain the log file.
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True, timeout=10,
                )
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def call(self, path, body=None):
        request = Request(
            self.base + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_production_http_games_and_assets(self):
        self.start()
        for asset in ("/", "/static/app.js", "/static/style.css"):
            with urlopen(self.base + asset, timeout=5) as response:
                self.assertEqual(response.status, 200)
        for difficulty, word in {"easy": "eagle", "medium": "compass", "hard": "xylophone"}.items():
            state = self.call("/api/games", {"difficulty": difficulty})
            path = "/api/games/" + state["game_id"]
            self.assertEqual(self.call(path), state)
            for letter in dict.fromkeys(word):
                self.assertNotIn("word", state)
                state = self.call(path + "/guess", {"letter": letter})
            self.assertEqual(state["status"], "won")
            self.assertEqual(state["word"], word)
        state = self.call("/api/games", {"difficulty": "easy"})
        path = "/api/games/" + state["game_id"]
        for letter in "zxcvbn":
            self.assertNotIn("word", state)
            state = self.call(path + "/guess", {"letter": letter})
        self.assertEqual(state["status"], "lost")
        with self.assertRaises(HTTPError) as failure:
            self.call(path + "/guess", {"letter": "e"})
        self.assertEqual(failure.exception.code, 400)
        self.assertEqual(set(json.load(failure.exception)), {"error"})
        failure.exception.close()
        self.log.flush()
        self.log.seek(0)
        logs = self.log.read()
        self.assertIn("Serving on", logs)
        self.assertNotIn("eagle", logs)
        self.assertNotIn("Traceback", logs)
        self.assertNotIn("Debugger", logs)

    def test_process_restart_clears_games(self):
        self.start()
        game_id = self.call("/api/games", {"difficulty": "easy"})["game_id"]
        self.stop(self.process)
        self.start()
        with self.assertRaises(HTTPError) as failure:
            self.call("/api/games/" + game_id)
        self.assertEqual(failure.exception.code, 404)
        self.assertEqual(set(json.load(failure.exception)), {"error"})
        failure.exception.close()

    def test_invalid_port_fails_before_startup(self):
        for port in ("invalid", "0", "65536", "-1"):
            with self.subTest(port=port):
                result = subprocess.run(
                    [sys.executable, str(self.directory / "production.py")],
                    env={**os.environ, "PORT": port},
                    capture_output=True, text=True, timeout=10,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("PORT must be an integer", result.stderr)
