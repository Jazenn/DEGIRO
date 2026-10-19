import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AllocationDonut } from './AllocationDonut';
import { CurrentAssetHoldingRecord } from '../types/portfolio';

describe('AllocationDonut Component', () => {
  const mockHoldings: CurrentAssetHoldingRecord[] = [
    {
      symbol: 'VWCE.DE',
      name: 'Vanguard FTSE All-World UCITS ETF',
      isin: 'IE00BK5BQT80',
      shares_held: 209.5,
      current_price_eur: 124.8,
      total_value_eur: 26145.6,
      total_cost_eur: 22890.0,
      unrealized_pnl_eur: 3255.6,
      actual_pct: 54.2,
      target_pct: 55.5,
      drift_pct: -1.3,
      recommended_action_eur: 625.0,
    },
    {
      symbol: 'EXUS.DE',
      name: 'iShares MSCI World ex-USA UCITS ETF',
      isin: 'IE0006WW1TQ4',
      shares_held: 185.0,
      current_price_eur: 56.1,
      total_value_eur: 10378.5,
      total_cost_eur: 9250.0,
      unrealized_pnl_eur: 1128.5,
      actual_pct: 21.5,
      target_pct: 21.0,
      drift_pct: 0.5,
      recommended_action_eur: 0.0,
    },
    {
      symbol: 'BTC-EUR',
      name: 'Bitcoin',
      isin: 'XFC000A2YY6Q',
      shares_held: 0.071,
      current_price_eur: 66500.0,
      total_value_eur: 4721.5,
      total_cost_eur: 3800.0,
      unrealized_pnl_eur: 921.5,
      actual_pct: 9.8,
      target_pct: 8.0,
      drift_pct: 1.8,
      recommended_action_eur: 0.0,
    },
  ];

  it('renders title and total assets count badge', () => {
    render(<AllocationDonut holdings={mockHoldings} totalPortfolioValue={41245.6} />);

    expect(screen.getByText('Asset Allocation')).toBeInTheDocument();
    expect(screen.getByText('3 Assets')).toBeInTheDocument();
  });

  it('renders SVG slices with correct accessible labels', () => {
    const { container } = render(
      <AllocationDonut holdings={mockHoldings} totalPortfolioValue={41245.6} />
    );

    const svg = container.querySelector('svg[aria-label="Asset Allocation Donut Chart"]');
    expect(svg).toBeInTheDocument();

    const slices = container.querySelectorAll('path[data-slice-symbol]');
    expect(slices.length).toBe(3);
    expect(slices[0].getAttribute('data-slice-symbol')).toBe('VWCE.DE');
  });

  it('displays actual % vs target % and visual drift badges in the legend', () => {
    render(<AllocationDonut holdings={mockHoldings} totalPortfolioValue={41245.6} />);

    // Check symbols
    expect(screen.getByText('VWCE.DE')).toBeInTheDocument();
    expect(screen.getByText('EXUS.DE')).toBeInTheDocument();
    expect(screen.getByText('BTC-EUR')).toBeInTheDocument();

    // Check actual vs target indicators
    expect(screen.getByText(/54.20%/)).toBeInTheDocument();
    expect(screen.getByText(/Target 55.50%/)).toBeInTheDocument();

    // Check drift badges: -1.3% Underweight, +1.8% Overweight, +0.5% Overweight
    expect(screen.getByText('-1.3% Underweight')).toBeInTheDocument();
    expect(screen.getByText('+1.8% Overweight')).toBeInTheDocument();
  });

  it('interactively updates center label when hovering a slice', () => {
    const { container } = render(
      <AllocationDonut holdings={mockHoldings} totalPortfolioValue={41245.6} />
    );

    // Initial center shows default portfolio or summary
    expect(screen.getByTestId('donut-center-title')).toHaveTextContent(/Portfolio Value|Allocation/);

    // Hover over VWCE.DE slice
    const vwceSlice = container.querySelector('path[data-slice-symbol="VWCE.DE"]');
    expect(vwceSlice).toBeInTheDocument();
    fireEvent.mouseEnter(vwceSlice!);

    expect(screen.getByTestId('donut-center-symbol')).toHaveTextContent('VWCE.DE');
    expect(screen.getByTestId('donut-center-pct')).toHaveTextContent('54.20%');

    // Unhover
    fireEvent.mouseLeave(vwceSlice!);
    expect(screen.queryByTestId('donut-center-symbol')).not.toBeInTheDocument();
  });

  it('handles empty holdings gracefully', () => {
    render(<AllocationDonut holdings={[]} totalPortfolioValue={0} />);

    expect(screen.getByText('Asset Allocation')).toBeInTheDocument();
    expect(screen.getByText('0 Assets')).toBeInTheDocument();
    expect(screen.getByText(/No assets currently in portfolio/i)).toBeInTheDocument();
  });
});
