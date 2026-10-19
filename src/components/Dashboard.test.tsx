import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
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

  it('displays the interactive performance curve with legend items', () => {
    render(<Dashboard initialData={demoData} />);

    expect(screen.getByText(/Portfolio Growth & Valuation/i)).toBeInTheDocument();
    expect(screen.getByText(/^Portfolio Value$/i)).toBeInTheDocument();
    expect(screen.getByText(/^Invested Capital$/i)).toBeInTheDocument();
  });

  it('shows demo indicator badge when loaded with demo data', () => {
    render(<Dashboard initialData={demoData} />);

    expect(screen.getByText(/Demo Mode/i)).toBeInTheDocument();
  });
});
