import functions_framework
from fetcher import main as run_fetcher

@functions_framework.http
def run_price_fetcher(request):
    """
    Cloud Function entry point.
    Triggered by an HTTP request (via Cloud Scheduler).
    """
    print("Cloud Function: Price Fetcher triggered.")
    try:
        # We call the existing main logic from fetcher.py
        run_fetcher()
        return "Success: Price fetcher completed.", 200
    except Exception as e:
        print(f"Error during execution: {str(e)}")
        return f"Error: {str(e)}", 500
