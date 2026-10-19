import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CryptoScaleCard } from './CryptoScaleCard';
import { PortfolioAssetSetting, CurrentAssetHoldingRecord } from '../types/portfolio';

describe('CryptoScaleCard', () => {
  const mockCryptoSettings: PortfolioAssetSetting[] = [
    {
      symbol: 'BTC-EUR',
      display_name: 'Bitcoin',
      target_pct: 8.0,
      buy_dip_trigger: 58500,
      sell_profit_trigger: 75420,
      is_crypto: true,
      buy_budget: 350,
    },
    {
      symbol: 'ETH-EUR',
      display_name: 'Ethereum',
      target_pct: 2.0,
      buy_dip_trigger: 2800,
      sell_profit_trigger: 3800,
      is_crypto: true,
      buy_budget: 150,
    },
  ];

  const mockHoldings: CurrentAssetHoldingRecord[] = [
    {
      symbol: 'BTC-EUR',
      name: 'Bitcoin',
      isin: 'XFC000A2YY6Q',
      shares_held: 0.071,
      current_price_eur: 64320,
      total_value_eur: 4566.72,
      total_cost_eur: 3800,
      unrealized_pnl_eur: 766.72,
      actual_pct: 9.8,
      target_pct: 8.0,
      drift_pct: 1.8,
      recommended_action_eur: 0,
    },
    {
      symbol: 'ETH-EUR',
      name: 'Ethereum',
      isin: 'XFC000A2YY6X',
      shares_held: 0.5,
      current_price_eur: 3210,
      total_value_eur: 1605,
      total_cost_eur: 1500,
      unrealized_pnl_eur: 105,
      actual_pct: 3.4,
      target_pct: 2.0,
      drift_pct: 1.4,
      recommended_action_eur: 0,
    },
  ];

  it('renders Crypto Scale title and current market price', () => {
    render(
      <CryptoScaleCard
        cryptoSettings={mockCryptoSettings}
        holdings={mockHoldings}
      />
    );

    expect(screen.getByText(/Crypto Scale/i)).toBeInTheDocument();
    expect(screen.getAllByText(/€64,320/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Bitcoin/i)).toBeInTheDocument();
  });

  it('displays predefined accumulation buy zones, profit targets, and budgets', () => {
    render(
      <CryptoScaleCard
        cryptoSettings={mockCryptoSettings}
        holdings={mockHoldings}
      />
    );

    // Buy dip trigger: €58,500
    expect(screen.getAllByText(/€58,500/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Budget: €350/i)).toBeInTheDocument();

    // Take-profit target: €75,420
    expect(screen.getAllByText(/€75,420/).length).toBeGreaterThan(0);
  });

  it('displays distance percentages relative to current price', () => {
    render(
      <CryptoScaleCard
        cryptoSettings={mockCryptoSettings}
        holdings={mockHoldings}
      />
    );

    // Distance to buy trigger: (58500 - 64320) / 64320 * 100 = -9.05%
    expect(screen.getByText(/-9\.0%|-9\.1%/)).toBeInTheDocument();

    // Distance to profit target: (75420 - 64320) / 64320 * 100 = +17.26%
    expect(screen.getByText(/\+17\.2%|\+17\.3%/)).toBeInTheDocument();
  });

  it('allows switching between configured crypto assets (e.g. BTC and ETH)', () => {
    render(
      <CryptoScaleCard
        cryptoSettings={mockCryptoSettings}
        holdings={mockHoldings}
      />
    );

    // Click on Ethereum tab
    const ethTab = screen.getByRole('button', { name: /ETH|Ethereum/i });
    fireEvent.click(ethTab);

    expect(screen.getAllByText(/€3,210/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/€2,800/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/€3,800/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Budget: €150/i)).toBeInTheDocument();
  });

  it('calls onOpenSettings callback when settings button or link is clicked', () => {
    const onOpenSettings = vi.fn();
    render(
      <CryptoScaleCard
        cryptoSettings={mockCryptoSettings}
        holdings={mockHoldings}
        onOpenSettings={onOpenSettings}
      />
    );

    const configureBtn = screen.getByRole('button', { name: /configure|adjust triggers|edit/i });
    fireEvent.click(configureBtn);

    expect(onOpenSettings).toHaveBeenCalledTimes(1);
  });

  it('displays Rebalancing Target label and dynamic take profit percentage', () => {
    const customSettings: PortfolioAssetSetting[] = [
      {
        ...mockCryptoSettings[0],
        sell_profit_pct: 25.0,
      },
    ];

    render(
      <CryptoScaleCard
        cryptoSettings={customSettings}
        holdings={mockHoldings}
      />
    );

    expect(screen.getByText('Rebalancing Target:')).toBeInTheDocument();
    expect(screen.getByText('Take 25% Profit')).toBeInTheDocument();
  });
});
