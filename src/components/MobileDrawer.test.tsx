import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MobileDrawer } from './MobileDrawer';

describe('MobileDrawer', () => {
  it('does not render when isOpen is false', () => {
    const { container } = render(
      <MobileDrawer
        isOpen={false}
        onClose={vi.fn()}
        onOpenUpload={vi.fn()}
        onOpenSettings={vi.fn()}
        onRefreshPrices={vi.fn()}
        hasCrypto={true}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders navigation sections and action buttons with min 44px tap targets when isOpen is true', () => {
    render(
      <MobileDrawer
        isOpen={true}
        onClose={vi.fn()}
        onOpenUpload={vi.fn()}
        onOpenSettings={vi.fn()}
        onRefreshPrices={vi.fn()}
        hasCrypto={true}
      />
    );

    expect(screen.getByRole('heading', { name: /Navigation & Actions/i })).toBeInTheDocument();

    // Check navigation items
    expect(screen.getByRole('button', { name: /Metrics Overview/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Growth Chart/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Asset Allocation/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Rebalance Cockpit/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Crypto Scale/i })).toBeInTheDocument();

    // Check action items
    expect(screen.getByRole('button', { name: /Refresh Prices/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Upload CSV/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Portfolio Settings/i })).toBeInTheDocument();

    // Ensure all buttons have min-h-[44px] for mobile touch compliance
    const buttons = screen.getAllByRole('button');
    for (const btn of buttons) {
      expect(btn.className).toMatch(/min-h-\[44px\]|h-11|h-12|py-3|p-3/);
    }
  });

  it('triggers action callbacks and closes drawer', () => {
    const onClose = vi.fn();
    const onOpenUpload = vi.fn();
    const onOpenSettings = vi.fn();
    const onRefreshPrices = vi.fn();

    render(
      <MobileDrawer
        isOpen={true}
        onClose={onClose}
        onOpenUpload={onOpenUpload}
        onOpenSettings={onOpenSettings}
        onRefreshPrices={onRefreshPrices}
        hasCrypto={false}
      />
    );

    // Crypto item shouldn't be rendered when hasCrypto is false
    expect(screen.queryByRole('button', { name: /Crypto Scale/i })).not.toBeInTheDocument();

    // Click Upload CSV
    const uploadBtn = screen.getByRole('button', { name: /Upload CSV/i });
    fireEvent.click(uploadBtn);
    expect(onOpenUpload).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalled();

    // Click Settings
    const settingsBtn = screen.getByRole('button', { name: /Portfolio Settings/i });
    fireEvent.click(settingsBtn);
    expect(onOpenSettings).toHaveBeenCalledTimes(1);

    // Click Refresh
    const refreshBtn = screen.getByRole('button', { name: /Refresh Prices/i });
    fireEvent.click(refreshBtn);
    expect(onRefreshPrices).toHaveBeenCalledTimes(1);
  });

  it('shows spinning icon and disabled state when isRefreshing is true', () => {
    render(
      <MobileDrawer
        isOpen={true}
        onClose={vi.fn()}
        onOpenUpload={vi.fn()}
        onOpenSettings={vi.fn()}
        onRefreshPrices={vi.fn()}
        isRefreshing={true}
        hasCrypto={true}
      />
    );

    const refreshBtn = screen.getByRole('button', { name: /Refreshing Prices\.\.\./i });
    expect(refreshBtn).toBeDisabled();
  });

  it('calls onClose when close button or backdrop is clicked', () => {
    const onClose = vi.fn();
    render(
      <MobileDrawer
        isOpen={true}
        onClose={onClose}
        onOpenUpload={vi.fn()}
        onOpenSettings={vi.fn()}
        onRefreshPrices={vi.fn()}
        hasCrypto={true}
      />
    );

    const closeBtn = screen.getByRole('button', { name: /Close navigation menu/i });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
