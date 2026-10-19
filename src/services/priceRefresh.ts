export interface PriceRefreshOptions {
  repo?: string;
  token?: string;
  ref?: string;
  isDemo?: boolean;
  delayMs?: number;
  customFetch?: typeof fetch;
}

export interface PriceRefreshResult {
  success: boolean;
  message: string;
  timestamp: string;
}

/**
 * Triggers an on-demand price refresh.
 *
 * If `isDemo` is true (or neither repo nor token is provided), it simulates an on-demand
 * refresh with a live timestamp update.
 * If `repo` and `token` are provided, it dispatches the GitHub Actions `price_fetcher.yml` workflow.
 */
export async function triggerPriceRefresh(
  options: PriceRefreshOptions = {}
): Promise<PriceRefreshResult> {
  const repo =
    options.repo ||
    (typeof import.meta !== 'undefined' && import.meta.env
      ? import.meta.env.VITE_GITHUB_REPO
      : undefined);

  const token =
    options.token ||
    (typeof import.meta !== 'undefined' && import.meta.env
      ? import.meta.env.VITE_GITHUB_TOKEN
      : undefined);

  const ref = options.ref || 'main';
  const fetchFn = options.customFetch || (typeof fetch !== 'undefined' ? fetch : undefined);

  // Demo simulation mode if explicitly requested or if GitHub credentials are not present
  if (options.isDemo || !repo || !token) {
    const delay = options.delayMs !== undefined ? options.delayMs : 600;
    if (delay > 0) {
      await new Promise((resolve) => setTimeout(resolve, delay));
    }

    return {
      success: true,
      message: 'Prices refreshed (Demo mode simulated)',
      timestamp: new Date().toISOString(),
    };
  }

  if (!fetchFn) {
    return {
      success: false,
      message: 'Fetch API is unavailable in this environment',
      timestamp: new Date().toISOString(),
    };
  }

  try {
    const url = `https://api.github.com/repos/${repo}/actions/workflows/price_fetcher.yml/dispatches`;
    const response = await fetchFn(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ref }),
    });

    if (response.status === 204 || response.ok) {
      return {
        success: true,
        message: 'Price fetcher workflow dispatched successfully',
        timestamp: new Date().toISOString(),
      };
    }

    const errText = await response.text();
    return {
      success: false,
      message: `GitHub API error (${response.status}): ${errText || response.statusText}`,
      timestamp: new Date().toISOString(),
    };
  } catch (err: any) {
    return {
      success: false,
      message: err?.message || 'Unknown network error dispatching price refresh',
      timestamp: new Date().toISOString(),
    };
  }
}
