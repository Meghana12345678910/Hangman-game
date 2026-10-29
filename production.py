"""Single-process production entry point for local checks and cloud hosting."""

import logging
import os

from waitress import serve

from server import create_app


def main():
    port_text = os.environ.get("PORT", "10000")
    try:
        port = int(port_text)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise SystemExit("PORT must be an integer between 1 and 65535.") from None

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = create_app()
    app.config.update(DEBUG=False, TESTING=False)
    # All games live in this process. Multiple processes/instances would each
    # have a different game dictionary; keep one instance on the cloud host.
    serve(app, host="0.0.0.0", port=port, threads=1)


if __name__ == "__main__":
    main()
