# Python Project

A Telegram bathroom timer bot that lets users start a timer and receive an
alert when they have been away longer than the configured limit.

## Getting started

```bash
cd python-project
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Set the `BOT_TOKEN` environment secret, then start the bot:

```bash
BOT_TOKEN=your-token python main.py
```

The bot responds to `/start`, provides a bathroom timer button, and sends an
alert after 10 minutes unless the user presses “กลับมาแล้ว”.

Run the tests:

```bash
python -m unittest discover
```

## Project layout

```text
python-project/
├── src/python_project/   # Application code
├── main.py               # Telegram bot entry point
├── tests/                # Automated tests
└── pyproject.toml        # Project metadata and tooling
```