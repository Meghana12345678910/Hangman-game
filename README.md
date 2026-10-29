# Hangman

Phases 1–5 implement and test the game engine, word management, Flask REST API, and browser client.
Python 3.10 or newer is required. Install Flask using the commands below.
Open `http://127.0.0.1:5000/` after starting the server to play in a browser.

From the project directory, set up an isolated environment in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

For a clean checkout from GitHub, run these commands from the parent directory
where you want the project:

```powershell
git clone https://github.com/Meghana12345678910/Hangman-game.git
cd Hangman-game
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe server.py
```

Install Google Chrome before running browser tests, then open
`http://127.0.0.1:5000/` to play. Stop the local server with Ctrl+C.
GitHub stores the source; the application runs locally until the deployment phase.

On macOS/Linux, use `.venv/bin/python` in place of
`.\.venv\Scripts\python.exe`. Activation is optional.

`game.py` exposes `HangmanGame(word)`, `guess(letter)`, and `to_state()`.
Supply a nonempty English A-Z word; words and single-letter guesses are normalized
to lowercase. Each game allows six incorrect guesses. Invalid, duplicate, and
post-game guesses raise `InvalidGuessError` without changing the game.
The public state includes the spaced pattern, guessed/incorrect letters,
remaining guesses, and status. The `word` field appears only after a win or loss.

`word_manager.py` exposes `WordManager(words_dir=None).random_word(difficulty)`.
The default directory is `words/` beside the module, independent of the current
working directory. Difficulty must be exactly `easy`, `medium`, or `hard`;
other values raise `InvalidDifficultyError`.

The three included files are small starter lists, not the original lists discussed
in the historical transcript. Store one English A-Z word per line. Loading strips
surrounding whitespace, normalizes case, ignores blank lines, and removes duplicates.
Missing/unreadable files, invalid entries, and empty lists raise `WordListError`
at startup. Entries use the same alphabet as the game engine.

Start the local server (debug disabled):

```powershell
.\.venv\Scripts\python.exe server.py
```

It listens at `http://127.0.0.1:5000`. Games are stored in this process only;
restarting clears them. This local development server is not a cloud deployment.

The API accepts JSON objects with exactly the fields shown:

| Method | Path | Body | Success |
|---|---|---|---|
| POST | `/api/games` | `{"difficulty":"easy"}` | 201 |
| GET | `/api/games/{game_id}` | none | 200 |
| POST | `/api/games/{game_id}/guess` | `{"letter":"e"}` | 200 |

All successful responses contain `game_id`, `pattern`, `guessed_letters`,
`incorrect_letters`, `remaining_guesses`, and `status`. Only finished games
include `word`. Duplicate, invalid, or post-game guesses return 400 without
changing the game. Malformed JSON, missing/extra fields, or an invalid difficulty
also return 400; unknown games return 404. Errors have the shape
`{"error":"message"}`. Non-JSON request bodies return 400.

For a manual HTTP check, use PowerShell in another terminal:

```powershell
$game = Invoke-RestMethod http://127.0.0.1:5000/api/games -Method Post -ContentType application/json -Body '{"difficulty":"easy"}'
Invoke-RestMethod "http://127.0.0.1:5000/api/games/$($game.game_id)"
Invoke-RestMethod "http://127.0.0.1:5000/api/games/$($game.game_id)/guess" -Method Post -ContentType application/json -Body '{"letter":"e"}'
```

Repeat the last request with other letters until `status` is `won` or `lost`.
The root URL serves the browser client. Select Easy, Medium, or Hard and click
New Game. Click letters or type A–Z using a physical keyboard. Used letters are
disabled; after a win/loss, New Game resets the word, history, and drawing.
Changing difficulty applies to the next new game. Reloading the page starts a
fresh client; it does not resume an earlier game.

To run browser tests as well as the backend suite, install the optional test dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Browser tests use installed Google Chrome in headless mode and a temporary local
Flask server with controlled words. Chrome must be installed; browser tests are
skipped when Playwright is absent. No Playwright browser download is required.
To run just the browser tests, use `-p test_browser.py` with unittest discovery.

For a fresh setup, create a new virtual environment, install `requirements-dev.txt`,
then run the full discovery command above. A successful complete run must include
the browser tests without skips. For backend-only verification, install
`requirements.txt`; browser tests will report skips.

Only one request runs at a time. After a failed guess response, the browser reads
the game's current state from the server because the guess may already have been
accepted. If this refresh fails too, guessing is disabled; restore the connection
and click New Game. A request times out after 15 seconds (a failed guess may need
another 15 seconds for its refresh). Failed requests are not automatically retried.

For debugging, use the browser Console for JavaScript errors and Network for
request method, path, status, and timing. The server terminal displays HTTP access
diagnostics. Do not copy active-game answers into diagnostic logs. The browser
tests simulate lost responses, offline mode, timeouts, and rapid input without
changing the API or adding server log/replay features.

Manual browser checklist (start the local server first):

1. Open `/` at desktop size. Confirm letters are disabled before New Game.
2. Start Easy. Type an uppercase letter and click another on-screen letter;
   confirm revealed positions, histories, and remaining lives match the responses.
   A correct letter must not add a body part; each wrong letter must add one.
3. Finish a win. Confirm the success message, final word, and disabled letters.
   Start again and finish a loss with six wrong letters; check all six body parts
   and the final word. Verify guessing stays disabled after either outcome.
4. Start a new game at each difficulty. Confirm the old history, drawing, and
   answer clear, lives reset to six, and letters become available.
5. Repeat at 390px and 320px viewport widths. Check there is no horizontal
   scrolling, the word wraps, and controls remain readable and tappable.
6. In developer tools, inspect create/guess JSON while playing: no `word` field
   should appear. Confirm it appears only when status becomes `won` or `lost`.
7. Use network throttling to observe loading feedback and disabled controls.
   Set the browser offline and make a request: confirm an error appears and
   New Game becomes available. Restore the connection and start a new game.
8. Rapidly click two letters and press keys while a request is pending. Confirm
   only the first guess is submitted; repeat an already guessed letter and type
   `1` or `!` to confirm no additional guess is sent.
9. Open a second tab and start another game. Guess in each tab and verify their
   patterns, lives, and histories stay independent.
10. Go offline during an active game and guess. After the error, check that
    guessing is disabled and New Game is enabled. Restore networking and start
    again; check that controls and the six-life state reset.

See `TODO.md` for the phased reduced assignment scope.

## Cloud deployment — Phase 7

Public application: https://hangman-game-z3k6.onrender.com/

Verified on October 29, 2026 against deployed application commit `0a15cae`
(commit and successful Waitress startup confirmed by the service owner in Render).
The served HTML, JavaScript, and CSS match the source for that deployment.
Live HTTPS checks passed for all three difficulties, physical and on-screen
keyboards, correct and incorrect guesses, wins/losses, New Game reset, JSON API
responses, rejected inputs, and hidden-answer protection. Chrome viewport checks
passed at 1280px, 390px, and 320px, with no horizontal overflow or JavaScript errors.
No runtime code fix was required.

Initial HTTPS response during verification: 0.43 seconds. This was not a controlled
idle cold-start measurement. The owner confirmed successful production startup
without startup errors; private Render logs were not directly accessible to the
verification process. Live requests returned expected statuses without unexpected
server errors. Process restart clearing games is covered by local production tests.

The repository includes a [Render Blueprint](https://render.com/docs/blueprint-spec)
in `render.yaml`. It runs the API, browser assets, and word lists as one Python
web service connected to this repository's `main` branch. The configured service
uses the Free plan and one instance. `.python-version` selects Python 3.14.2.

| Setting | Value |
|---|---|
| Build command | `pip install -r requirements.txt` |
| Start command | `python production.py` |
| Health check | `/` |
| Port | Render's `PORT` environment variable; local default `10000` |
| WSGI server | Waitress, one process and one request thread, debug disabled |

To check the production startup locally in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PORT = '10000'
.\.venv\Scripts\python.exe production.py
```

Open `http://127.0.0.1:10000/`. Stop with Ctrl+C. The existing `server.py`
development command continues to work on port 5000.

To recreate the deployment:

1. Sign in to [Render](https://dashboard.render.com), connect GitHub, and choose
   New > Blueprint for `Meghana12345678910/Hangman-game`, branch `main`.
2. Review `render.yaml` and create the service. If using New > Web Service
   instead, choose Python, Free, and the build/start commands above; retain one
   instance and the Python version from `.python-version`.
3. Wait for a successful deploy. Copy the actual HTTPS URL from the service
   dashboard into this section; do not assume it matches the configured name.
   Record the deployed Git commit shown in the dashboard.
4. Open that URL and repeat the manual browser checklist above. Check Easy,
   Medium, and Hard; finish a win and a loss and start another game. Inspect
   Network responses for no hidden answer during play. Run the README HTTP
   examples with the public base URL, including invalid inputs and unknown IDs.
5. Review the Render Events and Logs for build/start failures, tracebacks, and
   request failures. Waitress logs startup and errors, not request bodies or
   hidden words. Record observed results and cold-start timing here.

All games are in memory. A restart, redeploy, or service sleep clears them;
clients with old game IDs receive 404 and must choose New Game. Do not scale
above one instance/process. Concurrent requests are serialized by the existing
game lock. No database or persistent storage is introduced in this phase.

[Render's Free service documentation](https://render.com/docs/free) describes
spin-down after 15 minutes without traffic and a wake-up delay of about a minute.
This is provider guidance, not an observed cold-start timing for this application.
Open the browser page and wait for the service to wake before starting a game.
Real-phone touch testing, an idle wake-up measurement, and a public-service restart
check remain optional manual operational checks; they are not claimed as automated
verification results.

Repeat the opt-in live tests only against a service you own (they create in-memory
games). With `requirements-dev.txt` installed and Google Chrome available:

```powershell
$env:HANGMAN_DEPLOYMENT_URL = 'https://hangman-game-z3k6.onrender.com'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_live_deployment.py -v
```

Use `-m unittest discover -s tests -v` with the same environment variable to run
both the complete local suite and the live verification. With the variable unset,
the three live tests are skipped so normal development never contacts a deployment.
