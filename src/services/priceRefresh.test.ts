import { describe, it, expect, vi } from 'vitest';
import { triggerPriceRefresh, PriceRefreshResult } from './priceRefresh';

describe('priceRefresh service', () => {
  it('handles demo mode with simulated dispatch and live timestamp', async () => {
    const result: PriceRefreshResult = await triggerPriceRefresh({
      isDemo: true,
      delayMs: 10,
    });

    expect(result.success).toBe(true);
    expect(result.message).toContain('Demo');
    expect(result.timestamp).toBeDefined();
    expect(new Date(result.timestamp).getTime()).not.toBeNaN();
  });

  it('dispatches workflow to GitHub Actions when repo and token are configured', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      text: async () => '',
    });

    const result = await triggerPriceRefresh({
      repo: 'Jazenn/DEGIRO',
      token: 'ghp_secret_token_123',
      ref: 'main',
      customFetch: mockFetch as unknown as typeof fetch,
    });

    expect(mockFetch).toHaveBeenCalledWith(
      'https://api.github.com/repos/Jazenn/DEGIRO/actions/workflows/price_fetcher.yml/dispatches',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer ghp_secret_token_123',
          Accept: 'application/vnd.github.v3+json',
        }),
        body: JSON.stringify({ ref: 'main' }),
      })
    );

    expect(result.success).toBe(true);
    expect(result.message).toContain('workflow dispatched');
    expect(result.timestamp).toBeDefined();
  });

  it('dispatches repository_dispatch when dispatchType is repository_dispatch or eventType is provided', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      text: async () => '',
    });

    const result = await triggerPriceRefresh({
      repo: 'Jazenn/DEGIRO',
      token: 'ghp_secret_token_123',
      dispatchType: 'repository_dispatch',
      eventType: 'degiro_csv_uploaded',
      customFetch: mockFetch as unknown as typeof fetch,
    });

    expect(mockFetch).toHaveBeenCalledWith(
      'https://api.github.com/repos/Jazenn/DEGIRO/dispatches',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer ghp_secret_token_123',
          Accept: 'application/vnd.github.v3+json',
        }),
        body: JSON.stringify({
          event_type: 'degiro_csv_uploaded',
          client_payload: {},
        }),
      })
    );

    expect(result.success).toBe(true);
    expect(result.message).toContain('Repository dispatch');
  });

  it('returns failure details when GitHub API responds with error status', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      text: async () => 'Bad credentials',
    });

    const result = await triggerPriceRefresh({
      repo: 'Jazenn/DEGIRO',
      token: 'invalid_token',
      customFetch: mockFetch as unknown as typeof fetch,
    });

    expect(result.success).toBe(false);
    expect(result.message).toContain('401');
    expect(result.message).toContain('Bad credentials');
  });

  it('handles network or fetch exception gracefully', async () => {
    const mockFetch = vi.fn().mockRejectedValue(new Error('Network offline'));

    const result = await triggerPriceRefresh({
      repo: 'Jazenn/DEGIRO',
      token: 'ghp_token',
      customFetch: mockFetch as unknown as typeof fetch,
    });

    expect(result.success).toBe(false);
    expect(result.message).toContain('Network offline');
  });
});
