import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { DashboardShell } from './DashboardShell';

describe('replacement dashboard demonstration', () => {
  it('keeps synthetic data explicit while navigating every destination', () => {
    render(<DashboardShell />);
    expect(screen.getByText(/Synthetic demonstration/)).toBeInTheDocument();
    expect(screen.getAllByText('\u20ac1,100').length).toBeGreaterThan(0);
    expect(screen.getAllByText('+\u20ac95').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: 'Your money, clearly explained.' })).toBeInTheDocument();
    for (const [destination, heading] of [
      ['Performance', 'What changed over time?'],
      ['Costs', 'Understand recorded costs.'],
      ['Contributions', 'Choose your next contribution.'],
      ['Crypto Scale', 'Keep your core. Review your stages.'],
      ['Overview', 'Your money, clearly explained.'],
    ]) {
      fireEvent.click(screen.getByRole('button', { name: destination }));
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: destination })).toHaveAttribute('aria-current', 'page');
    }
    expect(screen.getByRole('link', { name: 'Open current dashboard' })).toHaveAttribute('href', '/');
  });
});
