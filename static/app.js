"use strict";

const ui = Object.fromEntries([
  "difficulty", "new-game", "pattern", "remaining", "message", "answer",
  "error", "keyboard", "guessed", "incorrect", "drawing-title"
].map(id => [id, document.getElementById(id)]));
const parts = [...document.querySelectorAll("[data-part]")];
let state = null;
let busy = false;
let needsRefresh = false;

for (const letter of "abcdefghijklmnopqrstuvwxyz") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "letter";
  button.textContent = letter.toUpperCase();
  button.dataset.letter = letter;
  button.setAttribute("aria-label", `Guess ${letter.toUpperCase()}`);
  button.addEventListener("click", () => guess(letter));
  ui.keyboard.append(button);
}

function render() {
  const playing = state?.status === "playing";
  ui["new-game"].disabled = busy;
  ui.difficulty.disabled = busy;
  document.querySelector(".game").setAttribute("aria-busy", String(busy));
  for (const button of ui.keyboard.children) {
    const letter = button.dataset.letter;
    const guessed = state?.guessed_letters.includes(letter) ?? false;
    const incorrect = state?.incorrect_letters.includes(letter) ?? false;
    button.disabled = busy || needsRefresh || !playing || guessed;
    button.classList.toggle("correct", guessed && !incorrect);
    button.classList.toggle("incorrect", incorrect);
  }
  ui.pattern.textContent = state?.pattern ?? "—";
  ui.guessed.textContent = state?.guessed_letters.join(" ").toUpperCase() || "None yet";
  ui.incorrect.textContent = state?.incorrect_letters.join(" ").toUpperCase() || "None yet";
  const mistakes = state?.incorrect_letters.length ?? 0;
  parts.forEach((part, index) => { part.toggleAttribute("hidden", index >= mistakes); });
  ui["drawing-title"].textContent = `Hangman: ${mistakes} incorrect guesses`;
  ui.remaining.textContent = state ? `${state.remaining_guesses} ${state.remaining_guesses === 1 ? "life" : "lives"} remaining` : "Six lives. A fresh start.";
  ui.answer.hidden = !state || playing;
  ui.answer.textContent = state && !playing ? `The word was ${state.word.toUpperCase()}.` : "";
  if (!busy) {
    ui.message.textContent = needsRefresh ? "Could not refresh this game. Start a new game to continue."
      : !state ? "Choose a difficulty, then start a new game."
      : playing ? "Pick a letter. You've got this."
      : state.status === "won" ? "You found it! Start a new game when you're ready."
      : "Out of lives. A new word is a fresh chance.";
  }
}

async function request(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The server could not complete that request.");
    return result;
  } finally {
    clearTimeout(timeout);
  }
}

async function perform(path, body, loading) {
  busy = true;
  ui.error.hidden = true;
  ui.error.textContent = "";
  ui.message.textContent = loading;
  render();
  try {
    state = await request(path, body);
    needsRefresh = false;
  } catch (error) {
    // A failed response does not mean the server rejected the guess. Read its
    // authoritative state instead of retrying a potentially accepted mutation.
    if (state && path.endsWith("/guess")) {
      try {
        state = await request(`/api/games/${encodeURIComponent(state.game_id)}`);
        needsRefresh = false;
      } catch {
        needsRefresh = true;
      }
    }
    ui.error.textContent = error.name === "AbortError"
      ? "The request timed out. Try again or start a new game."
      : error instanceof TypeError || error instanceof SyntaxError
        ? "Could not reach the game server. Check your connection and try again."
        : error.message;
    ui.error.hidden = false;
  } finally {
    busy = false;
    render();
  }
}

function guess(letter) {
  if (busy || needsRefresh || state?.status !== "playing" || state.guessed_letters.includes(letter)) return;
  return perform(`/api/games/${encodeURIComponent(state.game_id)}/guess`, { letter }, "Checking your letter…");
}

ui["new-game"].addEventListener("click", () => {
  if (!busy) perform("/api/games", { difficulty: ui.difficulty.value }, "Finding a new word…");
});

document.addEventListener("keydown", event => {
  if (event.ctrlKey || event.altKey || event.metaKey || event.repeat || event.isComposing) return;
  if (event.target.closest("input, select, textarea, [contenteditable='true']")) return;
  if (/^[a-z]$/i.test(event.key)) {
    event.preventDefault();
    guess(event.key.toLowerCase());
  }
});

render();
