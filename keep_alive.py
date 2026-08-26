"""Small Flask health server for external uptime monitors."""

from threading import Thread

from flask import Flask

app = Flask(__name__)


@app.get("/")
def health_check() -> tuple[str, int]:
    """Return a successful response while the bot process is alive."""
    return "Bot is alive!", 200


def keep_alive() -> Thread:
    """Run the health server in the background beside the Telegram bot."""
    server_thread = Thread(
        target=lambda: app.run(
            host="0.0.0.0",
            port=8080,
            debug=False,
            use_reloader=False,
        ),
        name="keep-alive-server",
        daemon=True,
    )
    server_thread.start()
    return server_thread