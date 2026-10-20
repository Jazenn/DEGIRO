"""Background pre-fetcher entrypoint delegating to backend.cli snapshot."""

from backend.cli import cmd_snapshot

if __name__ == "__main__":
    cmd_snapshot()
