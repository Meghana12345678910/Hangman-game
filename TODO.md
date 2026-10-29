# TODO — Reduced Hangman Assignment

Build only the game engine, word management, Flask REST API, browser client,
testing/debugging, GitHub repository, and cloud deployment.

Use the relevant game rules and API contract in `Specification.md`.
`cursor_transcript.md` is historical reference, not proof that this assignment
is complete. This reduced scope takes precedence over the broader specification.
Terminal clients, automated bots, evaluation mode, scoring, leaderboard, and
logging/replay features are out of scope.

Work one phase at a time. Pass its checkpoint and rerun earlier tests before
moving on. Check items off only after verifying them in this project; the old
completion marks do not carry forward. Keep the project runnable after each phase.

## Phase 1 — Project Setup and Game Engine

- [x] Set up the Python environment, dependencies, test directory, and basic README instructions.
- [x] Implement a Flask-independent `HangmanGame` with guessed/incorrect letters, a spaced masked word, six allowed incorrect guesses, and `playing`/`won`/`lost` states.
- [x] Normalize letter case; reject invalid, duplicate, and post-game guesses without changing state. Correct guesses reveal every occurrence without costing a life.
- [x] Serialize client-safe state; include `word` only after a win or loss.
- [x] Add unit tests for initial state, repeated letters, valid/invalid guesses, duplicates, wins, losses, and answer visibility.

**Checkpoint:** Engine tests pass without starting Flask or a browser.

## Phase 2 — Word Management

- [x] Use `words/easy.txt`, `words/medium.txt`, and `words/hard.txt`; normalize case, skip blank lines, remove duplicates, and validate alphabetic entries.
- [x] Select a random word by difficulty; handle invalid difficulties and missing, empty, or invalid word lists clearly.
- [x] Test loading and selection using controlled fixtures, including failure cases.

**Checkpoint:** Each difficulty returns a word from its own list, error cases pass,
and engine tests still pass.

## Phase 3 — Flask REST API

- [x] Combine the engine and word manager in Flask with unique game IDs and in-memory game storage.
- [x] Implement `POST /api/games`, `GET /api/games/{game_id}`, and `POST /api/games/{game_id}/guess` with the specification's JSON fields.
- [x] Return consistent JSON errors and appropriate HTTP status codes for malformed bodies, missing fields, invalid input, and unknown IDs.
- [x] Keep the server authoritative: clients choose difficulty and submit letters; they cannot supply the hidden word or game state.
- [x] Add Flask API tests for complete win/loss flows, independent games, validation, unchanged state after rejected guesses, and no answer disclosure while playing.

**Checkpoint:** Tests pass and a full game can be played through HTTP requests,
including retrieving its current state, before building the browser interface.

## Phase 4 — Browser Client

- [x] Serve HTML/CSS/JavaScript from Flask and communicate through the REST API using relative URLs.
- [x] Add difficulty selection, New Game, masked word, guessed/incorrect letters, remaining guesses, and a graphical Hangman that updates after mistakes.
- [x] Support physical and on-screen keyboards; disable guessed letters and guessing after a game ends.
- [x] Show loading/error feedback, win/loss messages, the final word, and a working new-game flow.
- [x] Make the interface usable at desktop and mobile sizes; derive all game results from server responses.

**Checkpoint:** Manually play a win and a loss, restart at each difficulty, and
check both keyboard methods and mobile layout. Inspect network responses to
confirm the answer stays hidden during play; rerun backend tests.

## Phase 5 — Integration Testing and Debugging

- [x] Test the browser-to-Flask flow end to end: create a game, guess, finish, and start another game.
- [x] Check invalid/repeated input, rapid clicks, API failures, and separate browser games; ensure errors do not leave controls stuck or corrupt displayed state.
- [x] Reproduce and fix defects using browser console/network tools and server diagnostics; add regression tests for meaningful bugs without recording hidden answers during play.
- [x] Document installation, local startup, test commands, the three API routes, and browser use; verify instructions from a fresh environment.

**Checkpoint:** All automated tests pass, browser checks have no unresolved
blocking defects, and a fresh local setup works using only the README.

## Phase 6 — GitHub Delivery

- [x] Initialize or verify Git, add an appropriate `.gitignore`, and exclude virtual environments, caches, and secrets.
- [x] Review the required assignment files, commit the verified work, and push to the intended GitHub repository.
- [x] Clone from GitHub into a clean location, install dependencies, run tests, and confirm browser play using the README.

**Checkpoint:** The GitHub version reproduces the tested local application.

## Phase 7 — Cloud Deployment

- [ ] Prepare a Python cloud web service connected to GitHub (Render is the transcript's example); document the chosen service's build/start settings.
- [ ] Use a production WSGI server with debug disabled and the host-provided port. Run one worker/instance while games are stored in memory.
- [ ] Deploy Flask and the browser together, including the word lists and static assets; record the public HTTPS URL in the README.
- [ ] Smoke-test the deployed browser and all three API routes: each difficulty, win/loss, restart, invalid requests, and hidden-word protection.
- [ ] Check deployment logs for startup/request failures and document that restarts clear games, plus any observed cold-start behavior.

**Checkpoint:** A fresh browser can play a complete game at the public URL,
remote API checks pass, and the documented GitHub revision matches the deployment.
