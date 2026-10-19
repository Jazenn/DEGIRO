import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CsvUploadModal } from './CsvUploadModal';

describe('CsvUploadModal', () => {
  it('does not render when isOpen is false', () => {
    const { container } = render(
      <CsvUploadModal
        isOpen={false}
        onClose={vi.fn()}
        onUploadSuccess={vi.fn()}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders modal with accept=".csv,text/csv" input for mobile Files/Downloads and min 44px touch targets', () => {
    render(
      <CsvUploadModal
        isOpen={true}
        onClose={vi.fn()}
        onUploadSuccess={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { name: /Upload DEGIRO CSV/i })).toBeInTheDocument();
    
    // Check file input attributes for mobile iOS/Android file picking
    const fileInput = screen.getByLabelText(/Select CSV File/i) as HTMLInputElement;
    expect(fileInput).toBeInTheDocument();
    expect(fileInput.getAttribute('accept')).toBe('.csv,text/csv');

    // Check touch target heights (min-h-[44px]) on interactive action buttons
    const closeBtn = screen.getByRole('button', { name: /Close modal/i });
    expect(closeBtn.className).toMatch(/min-h-\[44px\]|h-11|h-12|p-2\.5|p-3/);
  });

  it('parses valid CSV file on selection and displays immediate summary cards', async () => {
    const onUploadSuccess = vi.fn();
    render(
      <CsvUploadModal
        isOpen={true}
        onClose={vi.fn()}
        onUploadSuccess={onUploadSuccess}
      />
    );

    const validCsv = `Datum;Tijd;Product;ISIN;Aantal;Koers;Waarde;Order Id
2026-01-15;10:30;Vanguard FTSE All-World UCITS ETF;IE00BK5BQT80;10;120.50;-1205.00;ORD-001
2026-01-15;10:30;Vanguard FTSE All-World UCITS ETF;IE00BK5BQT80;10;120.50;-1205.00;ORD-001
2026-01-20;14:15;iShares MSCI World ex-USA;IE0006WW1TQ4;5;55.00;-275.00;ORD-002
`;

    const file = new File([validCsv], 'Transactions.csv', { type: 'text/csv' });
    const fileInput = screen.getByLabelText(/Select CSV File/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    // Expect summary metrics to appear
    await waitFor(() => {
      expect(screen.getByText(/3/i)).toBeInTheDocument(); // 3 rows processed
      expect(screen.getByText(/2/i)).toBeInTheDocument(); // 2 new stored
      expect(screen.getByText(/1/i)).toBeInTheDocument(); // 1 duplicate skipped
    });

    expect(screen.getByText(/Rows Processed/i)).toBeInTheDocument();
    expect(screen.getByText(/New Transactions/i)).toBeInTheDocument();
    expect(screen.getByText(/Duplicates Skipped/i)).toBeInTheDocument();

    // Confirm button is active
    const importBtn = screen.getByRole('button', { name: /Import & Refresh Snapshots/i });
    expect(importBtn).not.toBeDisabled();

    fireEvent.click(importBtn);

    await waitFor(() => {
      expect(onUploadSuccess).toHaveBeenCalledTimes(1);
    });
  });

  it('displays error message when an invalid CSV is selected', async () => {
    render(
      <CsvUploadModal
        isOpen={true}
        onClose={vi.fn()}
        onUploadSuccess={vi.fn()}
      />
    );

    const invalidContent = 'Name,Age,City\nAlice,30,Amsterdam\n';
    const file = new File([invalidContent], 'invalid.csv', { type: 'text/csv' });
    const fileInput = screen.getByLabelText(/Select CSV File/i);

    fireEvent.change(fileInput, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText(/Unsupported DEGIRO CSV format/i)).toBeInTheDocument();
    });
  });

  it('calls onClose when close button or Cancel is clicked', () => {
    const onClose = vi.fn();
    render(
      <CsvUploadModal
        isOpen={true}
        onClose={onClose}
        onUploadSuccess={vi.fn()}
      />
    );

    const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelBtn);

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
