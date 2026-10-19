import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Dashboard from './Dashboard';
import { getDemoDashboardData } from '../services/portfolioData';

describe('Dashboard Component', () => {
  const demoData = getDemoDashboardData();

  it('renders all key metric cards with formatted currency and mono fonts', async () => {
    render(<Dashboard initialData={demoData} />);

    // Total Portfolio Value
    expect(screen.getByText(/Total Portfolio Value/i)).toBeInTheDocument();
    expect(screen.getByText('€48,250.75')).toBeInTheDocument();

    // Net Invested
    expect(screen.getByText(/Net Invested/i)).toBeInTheDocument();
    expect(screen.getByText('€42,238.45')).toBeInTheDocument();

    // Total Gain / Loss
    expect(screen.getByText(/Total Gain \/ Loss/i)).toBeInTheDocument();
    expect(screen.getByText(/\+€6,012\.30/i)).toBeInTheDocument();
    expect(screen.getByText(/\+14\.23%/i)).toBeInTheDocument();

    // Free Cash
    expect(screen.getByText(/Free Cash/i)).toBeInTheDocument();
    expect(screen.getByText('€1,420.50')).toBeInTheDocument();
  });

  it('renders timeframe selector buttons with 1M, 3M, 1Y, ALL', () => {
    render(<Dashboard initialData={demoData} />);

    expect(screen.getByRole('button', { name: /^1M$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^3M$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^1Y$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^ALL$/i })).toBeInTheDocument();
  });

  it('switches timeframe when button is clicked', async () => {
    render(<Dashboard initialData={demoData} />);

    const btn1M = screen.getByRole('button', { name: /^1M$/i });
    const btnAll = screen.getByRole('button', { name: /^ALL$/i });

    // Initial state: ALL is active
    expect(btnAll).toHaveAttribute('data-active', 'true');
    expect(btn1M).toHaveAttribute('data-active', 'false');

    // Click 1M
    fireEvent.click(btn1M);

    expect(btn1M).toHaveAttribute('data-active', 'true');
    expect(btnAll).toHaveAttribute('data-active', 'false');
  });

  it('displays the interactive portfolio history growth with legend items', () => {
    render(<Dashboard initialData={demoData} />);

    expect(screen.getByText(/Portfolio Growth & Valuation/i)).toBeInTheDocument();
    expect(screen.getAllByText(/^Portfolio Value$/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/^Invested Capital$/i)).toBeInTheDocument();
  });

  it('shows demo indicator badge when loaded with demo data', () => {
    render(<Dashboard initialData={demoData} />);

    expect(screen.getByText(/Demo Mode/i)).toBeInTheDocument();
  });

  it('renders asset allocation donut chart and drift indicators in the dashboard', () => {
    render(<Dashboard initialData={demoData} />);

    expect(screen.getByText('Asset Allocation')).toBeInTheDocument();
    expect(screen.getByText('5 Assets')).toBeInTheDocument();
    expect(screen.getAllByText('VWCE.DE').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('-1.3% Underweight')).toBeInTheDocument();
    expect(screen.getByText('+1.8% Overweight')).toBeInTheDocument();
  });

  it('renders interactive monthly rebalancing cockpit below valuation chart', () => {
    render(<Dashboard initialData={demoData} />);

    expect(screen.getByText('Interactive Rebalancing Cockpit')).toBeInTheDocument();
    expect(screen.getByTestId('deposit-slider')).toBeInTheDocument();
    expect(screen.getByTestId('deposit-number-input')).toBeInTheDocument();
    expect(screen.getByTestId('current-deposit-label')).toBeInTheDocument();
    expect(screen.getByTestId('post-rebalance-drift')).toBeInTheDocument();
  });

  it('renders Crypto Scale card and displays current market price relative to triggers', () => {
    render(<Dashboard initialData={demoData} />);

    expect(screen.getByText(/Crypto Scale/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Accumulation Buy Zone/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Tier 1 Profit Target/i).length).toBeGreaterThan(0);
  });

  it('renders settings gear button in header and opens settings modal on click', () => {
    render(<Dashboard initialData={demoData} />);

    const settingsBtn = screen.getByRole('button', { name: /Strategy and Crypto Settings|Settings/i });
    expect(settingsBtn).toBeInTheDocument();

    fireEvent.click(settingsBtn);

    expect(screen.getByText(/Portfolio Strategy & Crypto Scale Settings/i)).toBeInTheDocument();
  });

  it('immediately updates target percentages and recalculates drift when saved from settings modal', async () => {
    render(<Dashboard initialData={demoData} />);

    // Open settings modal
    const settingsBtn = screen.getByRole('button', { name: /Strategy and Crypto Settings|Settings/i });
    fireEvent.click(settingsBtn);

    // Change VWCE target from 55.5 to 60.0
    const vwceInput = screen.getByLabelText(/Vanguard FTSE All-World|VWCE/i);
    fireEvent.change(vwceInput, { target: { value: '60.0' } });

    // Change Clean Energy target from 5.0 to 0.5 (so total remains 100%)
    const cleanEnergyInput = screen.getByLabelText(/Clean Energy/i);
    fireEvent.change(cleanEnergyInput, { target: { value: '0.5' } });

    // Save
    const saveBtn = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(saveBtn);

    // Modal should close and VWCE drift in donut breakdown should update to reflect 60.0% target
    // VWCE actual_pct is 54.2%, new target is 60.0% -> drift is -5.8% Underweight
    await waitFor(() => {
      expect(screen.getByText('-5.8% Underweight')).toBeInTheDocument();
    });
  });

  it('renders mobile menu button and opens mobile drawer on click', () => {
    render(<Dashboard initialData={demoData} />);

    const menuBtn = screen.getByRole('button', { name: /Open navigation menu/i });
    expect(menuBtn).toBeInTheDocument();

    fireEvent.click(menuBtn);

    expect(screen.getByRole('heading', { name: /Navigation & Actions/i })).toBeInTheDocument();
  });

  it('renders upload CSV button and opens CSV upload modal on click', () => {
    render(<Dashboard initialData={demoData} />);

    const uploadBtn = screen.getByRole('button', { name: /Upload CSV/i });
    expect(uploadBtn).toBeInTheDocument();

    fireEvent.click(uploadBtn);

    expect(screen.getByRole('heading', { name: /Upload DEGIRO CSV/i })).toBeInTheDocument();
  });

  it('triggers on-demand price refresh and shows toast notification upon completion', async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    render(<Dashboard initialData={demoData} onRefresh={onRefresh} />);

    const refreshBtn = screen.getByRole('button', { name: /Refresh Prices|Refresh/i });
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(onRefresh).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(screen.getByRole('status')).toBeInTheDocument();
      expect(screen.getByText(/Prices refreshed/i)).toBeInTheDocument();
    });
  });
});


