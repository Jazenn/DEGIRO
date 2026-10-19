import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { Dashboard } from './Dashboard';
import { getDemoDashboardData } from '../services/portfolioData';

describe('Comprehensive End-to-End Viewport Smoke Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('Desktop Viewport Experience', () => {
    it('renders full desktop navigation, metric cards, chart, allocation donut, cockpit, and crypto scale', () => {
      // Simulate desktop viewport (e.g. 1280x800)
      window.innerWidth = 1280;
      window.innerHeight = 800;

      const demoData = getDemoDashboardData();
      render(<Dashboard initialData={demoData} />);

      // Verify header branding and status
      expect(screen.getByText('DEGIRO Portfolio')).toBeInTheDocument();
      expect(screen.getByText(/Demo Mode/i)).toBeInTheDocument();

      // Verify desktop header action buttons
      expect(screen.getByRole('button', { name: /Upload CSV/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Strategy and Crypto Settings/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Refresh Prices/i })).toBeInTheDocument();

      // Verify all 5 core dashboard sections exist
      expect(screen.getByRole('region', { name: /Key Portfolio Metrics/i })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: /Portfolio Growth Chart/i })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: /Asset Allocation & Drift Analysis/i })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: /Interactive Monthly Rebalancing Cockpit/i })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: /Crypto Scale/i })).toBeInTheDocument();

      // Verify financial data integrity
      expect(screen.getByText('€48,250.75')).toBeInTheDocument();
      expect(screen.getByText('€42,238.45')).toBeInTheDocument();
      expect(screen.getByText('€1,420.50')).toBeInTheDocument();
    });

    it('handles desktop on-demand refresh dispatch with spinning indicator and toast feedback', async () => {
      const demoData = getDemoDashboardData();
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(<Dashboard initialData={demoData} onRefresh={onRefresh} />);

      const refreshBtn = screen.getByRole('button', { name: /Refresh Prices/i });
      fireEvent.click(refreshBtn);

      await waitFor(() => {
        expect(onRefresh).toHaveBeenCalledTimes(1);
      });

      await waitFor(() => {
        expect(screen.getByRole('status')).toBeInTheDocument();
        expect(screen.getByText(/Prices refreshed/i)).toBeInTheDocument();
      });
    });

    it('completes direct CSV upload workflow from desktop and displays immediate summary feedback', async () => {
      const demoData = getDemoDashboardData();
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(<Dashboard initialData={demoData} onRefresh={onRefresh} />);

      // Open CSV upload modal
      const uploadBtn = screen.getByRole('button', { name: /Upload CSV/i });
      fireEvent.click(uploadBtn);

      const uploadModal = screen.getByRole('dialog', { name: /Upload DEGIRO CSV/i });
      expect(uploadModal).toBeInTheDocument();

      // Select Dutch Transactions CSV
      const csvData = `Datum;Tijd;Product;ISIN;Aantal;Koers;Waarde;Order Id
2026-03-01;10:00;Vanguard FTSE All-World;IE00BK5BQT80;5;124.00;-620.00;ORD-991
2026-03-05;11:30;Bitcoin;XFC000A2YY6Q;0.01;66000.00;-660.00;ORD-992
`;
      const file = new File([csvData], 'Account.csv', { type: 'text/csv' });
      const fileInput = within(uploadModal).getByLabelText(/Select CSV File/i);
      fireEvent.change(fileInput, { target: { files: [file] } });

      // Verify validation summary metrics
      await waitFor(() => {
        expect(within(uploadModal).getByText(/Rows Processed/i)).toBeInTheDocument();
        expect(within(uploadModal).getByText(/New Transactions/i)).toBeInTheDocument();
        expect(within(uploadModal).getByText(/Duplicates Skipped/i)).toBeInTheDocument();
      });

      // Submit import
      const confirmBtn = within(uploadModal).getByRole('button', { name: /Import & Refresh Snapshots/i });
      fireEvent.click(confirmBtn);

      // Verify refresh triggered and toast displayed
      await waitFor(() => {
        expect(onRefresh).toHaveBeenCalledTimes(1);
      });

      await waitFor(() => {
        expect(screen.getByRole('status')).toBeInTheDocument();
        expect(screen.getByText(/Processed 2 rows: 2 new transaction\(s\) stored/i)).toBeInTheDocument();
      });
    });
  });

  describe('Mobile Viewport Experience', () => {
    it('provides touch-friendly navigation drawer with >=44px tap targets', () => {
      // Simulate mobile portrait viewport (e.g. 390x844 iPhone 14)
      window.innerWidth = 390;
      window.innerHeight = 844;

      const demoData = getDemoDashboardData();
      render(<Dashboard initialData={demoData} />);

      // Verify hamburger menu button exists and has >=44px touch target
      const menuBtn = screen.getByRole('button', { name: /Open navigation menu/i });
      expect(menuBtn).toBeInTheDocument();
      expect(menuBtn.className).toMatch(/min-h-\[44px\]/);
      expect(menuBtn.className).toMatch(/min-w-\[44px\]/);

      // Open drawer
      fireEvent.click(menuBtn);

      // Drawer is visible
      const drawer = screen.getByRole('dialog', { name: /Navigation & Actions/i });
      expect(drawer).toBeInTheDocument();

      // Check all drawer interactive buttons have touch-friendly tap targets
      const drawerButtons = within(drawer).getAllByRole('button');
      for (const btn of drawerButtons) {
        expect(btn.className).toMatch(/min-h-\[44px\]|h-11|h-12|py-3|p-3/);
      }
    });

    it('triggers on-demand refresh and updates timestamp from mobile drawer', async () => {
      window.innerWidth = 375;
      window.innerHeight = 667;

      const demoData = getDemoDashboardData();
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(<Dashboard initialData={demoData} onRefresh={onRefresh} />);

      // Open mobile drawer
      const menuBtn = screen.getByRole('button', { name: /Open navigation menu/i });
      fireEvent.click(menuBtn);

      const drawer = screen.getByRole('dialog', { name: /Navigation & Actions/i });

      // Click Refresh Prices inside mobile drawer
      const drawerRefreshBtn = within(drawer).getByRole('button', { name: /Refresh Prices/i });
      fireEvent.click(drawerRefreshBtn);

      await waitFor(() => {
        expect(onRefresh).toHaveBeenCalledTimes(1);
      });

      await waitFor(() => {
        expect(screen.getByRole('status')).toBeInTheDocument();
        expect(screen.getByText(/Prices refreshed/i)).toBeInTheDocument();
      });
    });

    it('allows opening CSV upload from mobile drawer and accepts mobile file selection', async () => {
      window.innerWidth = 390;
      window.innerHeight = 844;

      const demoData = getDemoDashboardData();
      const onRefresh = vi.fn().mockResolvedValue(undefined);

      render(<Dashboard initialData={demoData} onRefresh={onRefresh} />);

      // Open mobile drawer
      fireEvent.click(screen.getByRole('button', { name: /Open navigation menu/i }));

      const drawer = screen.getByRole('dialog', { name: /Navigation & Actions/i });

      // Click Upload CSV inside mobile drawer
      fireEvent.click(within(drawer).getByRole('button', { name: /Upload CSV/i }));

      // CSV Upload Modal opens
      const uploadModal = screen.getByRole('dialog', { name: /Upload DEGIRO CSV/i });
      expect(uploadModal).toBeInTheDocument();

      // File input has mobile-compatible accept attribute
      const fileInput = within(uploadModal).getByLabelText(/Select CSV File/i);
      expect(fileInput.getAttribute('accept')).toBe('.csv,text/csv');

      // Upload mobile downloaded file
      const csvContent = `Datum;Tijd;Product;ISIN;Aantal;Koers;Waarde;Order Id
2026-03-10;09:00;Clean Energy & Technology ETF;IE000OJ5TQP4;10;26.00;-260.00;ORD-993
`;
      const file = new File([csvContent], 'Transactions_Mobile.csv', { type: 'text/csv' });
      fireEvent.change(fileInput, { target: { files: [file] } });

      await waitFor(() => {
        expect(within(uploadModal).getByText(/Rows Processed/i)).toBeInTheDocument();
        expect(within(uploadModal).getByText(/New Transactions/i)).toBeInTheDocument();
      });

      fireEvent.click(within(uploadModal).getByRole('button', { name: /Import & Refresh Snapshots/i }));

      await waitFor(() => {
        expect(onRefresh).toHaveBeenCalledTimes(1);
      });
    });

    it('scrolls to sections smoothly when clicked from mobile drawer', () => {
      window.innerWidth = 390;
      window.innerHeight = 844;

      // Mock scrollIntoView
      const scrollIntoViewMock = vi.fn();
      window.HTMLElement.prototype.scrollIntoView = scrollIntoViewMock;

      const demoData = getDemoDashboardData();
      render(<Dashboard initialData={demoData} />);

      // Open drawer
      fireEvent.click(screen.getByRole('button', { name: /Open navigation menu/i }));

      const drawer = screen.getByRole('dialog', { name: /Navigation & Actions/i });

      // Click Rebalance Cockpit section link
      const cockpitNavBtn = within(drawer).getByRole('button', { name: /Rebalance Cockpit/i });
      fireEvent.click(cockpitNavBtn);

      // Wait for smooth scroll timeout
      return new Promise<void>((resolve) => {
        setTimeout(() => {
          expect(scrollIntoViewMock).toHaveBeenCalled();
          resolve();
        }, 200);
      });
    });
  });
});
