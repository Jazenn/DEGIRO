"""Cloud Function / Cloud Run entrypoint for background snapshot & price fetcher."""

from __future__ import annotations

import functions_framework
from backend.cli import cmd_snapshot


@functions_framework.http
def run_price_fetcher(request):
    """Cloud Function entry point triggered via HTTP (Cloud Scheduler)."""
    print("Cloud Function: Price Fetcher / Snapshot triggered.")
    try:
        cmd_snapshot()
        return "Success: Snapshot completed.", 200
    except Exception as e:
        print(f"Error during snapshot execution: {e}")
        return f"Error: {e}", 500


if __name__ == "__main__":
    cmd_snapshot()
