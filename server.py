"""Flask REST API for server-owned, in-memory Hangman games."""

from threading import Lock
from uuid import uuid4

from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, HTTPException, NotFound

from game import HangmanGame, InvalidGuessError
from word_manager import InvalidDifficultyError, WordManager


def create_app(word_manager: WordManager | None = None) -> Flask:
    app = Flask(__name__, static_folder="static")
    manager = word_manager if word_manager is not None else WordManager()
    games: dict[str, HangmanGame] = {}
    lock = Lock()

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.errorhandler(HTTPException)
    def http_error(error):
        response = error.get_response()
        response.data = app.json.dumps({"error": error.description})
        response.content_type = "application/json"
        return response

    def body_with(field):
        if not request.is_json:
            raise BadRequest("Request must contain a JSON object.")
        body = request.get_json()
        if not isinstance(body, dict) or set(body) != {field}:
            raise BadRequest(f"Request must contain only '{field}'.")
        return body[field]

    def find_game(game_id):
        if game_id not in games:
            raise NotFound("Game not found.")
        return games[game_id]

    @app.post("/api/games")
    def create_game():
        difficulty = body_with("difficulty")
        try:
            game = HangmanGame(manager.random_word(difficulty))
        except InvalidDifficultyError as error:
            raise BadRequest(str(error)) from error
        with lock:
            game_id = uuid4().hex
            while game_id in games:
                game_id = uuid4().hex
            games[game_id] = game
            return jsonify(game_id=game_id, **game.to_state()), 201

    @app.get("/api/games/<game_id>")
    def get_game(game_id):
        with lock:
            return jsonify(game_id=game_id, **find_game(game_id).to_state())

    @app.post("/api/games/<game_id>/guess")
    def guess(game_id):
        with lock:
            game = find_game(game_id)
            letter = body_with("letter")
            try:
                state = game.guess(letter)
            except InvalidGuessError as error:
                raise BadRequest(str(error)) from error
            return jsonify(game_id=game_id, **state)

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
