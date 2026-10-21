import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { RebalanceCockpit } from './RebalanceCockpit';
import { CurrentAssetHoldingRecord } from '../types/portfolio';

describe('RebalanceCockpit Component', () => {
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
      is_crypto: false,
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
      is_crypto: false,
    },
    {
      symbol: 'IMAE.AS',
      name: 'iShares European Property Yield',
      isin: 'IE00B4K48X80',
      shares_held: 49.8,
      current_price_eur: 78.45,
      total_value_eur: 3906.81,
      total_cost_eur: 3600.0,
      unrealized_pnl_eur: 306.81,
      actual_pct: 8.1,
      target_pct: 8.5,
      drift_pct: -0.4,
      recommended_action_eur: 175.0,
      is_crypto: false,
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
      is_crypto: true,
    },
  ];

  it('renders rebalance cockpit header and default deposit amount of €800', () => {
    render(<RebalanceCockpit holdings={mockHoldings} totalPortfolioValue={45152.41} />);

    expect(screen.getByText(/Monthly Inflow Rebalancing/i)).toBeInTheDocument();
    expect(screen.getAllByDisplayValue('800')).toHaveLength(2);
    expect(screen.getByTestId('deposit-slider')).toHaveValue('800');
    expect(screen.getByTestId('deposit-number-input')).toHaveValue(800);
    expect(screen.getByTestId('current-deposit-label')).toHaveTextContent('€800.00');
  });

  it('renders rebalancing recommendations with exact EUR amounts and estimated share quantities', () => {
    render(<RebalanceCockpit holdings={mockHoldings} totalPortfolioValue={45152.41} />);

    // Underweight assets should show recommended EUR amounts and share estimates
    expect(screen.getByText('VWCE.DE')).toBeInTheDocument();
    expect(screen.getByText('IMAE.AS')).toBeInTheDocument();
    expect(screen.getByText('EXUS.DE')).toBeInTheDocument();

    // Check that share estimate text is rendered
    expect(screen.getByText(/shares @ €124.80/)).toBeInTheDocument();
    expect(screen.getByText(/shares @ €78.45/)).toBeInTheDocument();

    // Overweight asset (EXUS.DE) receives €0.00 and no purchase notice
    expect(screen.getAllByText(/Overweight \/ on target: no purchase needed/i).length).toBeGreaterThan(0);
  });

  it('enforces whole shares for stocks (e.g. whole number of shares, not 0.8)', () => {
    render(<RebalanceCockpit holdings={mockHoldings} totalPortfolioValue={45152.41} initialDeposit={100} />);

    // For deposit of €100, VWCE (€124.80) should recommend 1 whole share, not 0.8
    const card = screen.getByTestId('rebalance-card-VWCE.DE');
    expect(card).toBeInTheDocument();
    expect(card).toHaveTextContent('Approx. 1 shares @ €124.80');
    expect(card).toHaveTextContent('+€124.80');
  });

  it('renders optional allow-selling toggle and activates sell recommendations when toggled on', () => {
    render(<RebalanceCockpit holdings={mockHoldings} totalPortfolioValue={45152.41} initialDeposit={100} />);

    const toggle = screen.getByTestId('allow-selling-toggle');
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute('aria-checked', 'false');

    // Before toggling: BTC is overweight, no sells
    expect(screen.queryByText(/Sell to Rebalance/i)).not.toBeInTheDocument();

    // Click toggle to enable selling
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'true');

    // After toggling: overweight assets should show sell recommendations
    expect(screen.getAllByText(/Sell to Rebalance/i).length).toBeGreaterThan(0);
    const btcCard = screen.getByTestId('rebalance-card-BTC-EUR');
    expect(btcCard).toHaveTextContent(/Sell approx\./);

    // Badges in header
    expect(screen.getByTestId('total-sells-badge')).toBeInTheDocument();
    expect(screen.getByTestId('total-buys-badge')).toBeInTheDocument();
  });

  it('dynamically recalculates recommendations when changing deposit amount via number input', () => {
    render(<RebalanceCockpit holdings={mockHoldings} totalPortfolioValue={45152.41} />);

    const numberInput = screen.getByTestId('deposit-number-input');

    // Change deposit to 1500
    fireEvent.change(numberInput, { target: { value: '1500' } });

    expect(screen.getByTestId('current-deposit-label')).toHaveTextContent('€1,500.00');
  });

  it('dynamically recalculates recommendations when moving deposit slider', () => {
    render(<RebalanceCockpit holdings={mockHoldings} totalPortfolioValue={45152.41} />);

    const slider = screen.getByTestId('deposit-slider');

    // Change slider to 500
    fireEvent.change(slider, { target: { value: '500' } });

    expect(screen.getByTestId('current-deposit-label')).toHaveTextContent('€500.00');
  });

  it('allows quick preset selection', () => {
    render(<RebalanceCockpit holdings={mockHoldings} totalPortfolioValue={45152.41} />);

    const presetBtn = screen.getByRole('button', { name: '€1,000' });
    fireEvent.click(presetBtn);

    expect(screen.getByTestId('current-deposit-label')).toHaveTextContent('€1,000.00');
  });

  it('displays post-rebalance drift indicator', () => {
    render(<RebalanceCockpit holdings={mockHoldings} totalPortfolioValue={45152.41} />);

    expect(screen.getByTestId('post-rebalance-drift')).toBeInTheDocument();
  });

  it('handles empty holdings list without crashing', () => {
    render(<RebalanceCockpit holdings={[]} totalPortfolioValue={0} />);

    expect(screen.getByText(/No assets available to rebalance/i)).toBeInTheDocument();
  });
});
