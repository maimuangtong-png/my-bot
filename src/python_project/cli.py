"""Command-line interface for Python Project."""


def greeting(name: str = "Python Project") -> str:
    """Return a friendly greeting."""
    return f"Hello from {name}!"


def main() -> None:
    """Run the command-line application."""
    print(greeting())