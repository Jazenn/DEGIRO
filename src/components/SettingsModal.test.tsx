import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SettingsModal } from './SettingsModal';
import { PortfolioAssetSetting } from '../types/portfolio';

describe('SettingsModal', () => {
  const initialSettings: PortfolioAssetSetting[] = [
    {
      symbol: 'VWCE.DE',
      display_name: 'All-World ETF',
      target_pct: 55.5,
      buy_dip_trigger: null,
      sell_profit_trigger: null,
      is_crypto: false,
      buy_budget: null,
    },
    {
      symbol: 'EXUS.DE',
      display_name: 'Ex-USA ETF',
      target_pct: 21.0,
      buy_dip_trigger: null,
      sell_profit_trigger: null,
      is_crypto: false,
      buy_budget: null,
    },
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
      symbol: 'IMAE.AS',
      display_name: 'Europe ETF',
      target_pct: 8.5,
      buy_dip_trigger: null,
      sell_profit_trigger: null,
      is_crypto: false,
      buy_budget: null,
    },
    {
      symbol: 'ASWC.DE',
      display_name: 'Clean Energy',
      target_pct: 7.0,
      buy_dip_trigger: null,
      sell_profit_trigger: null,
      is_crypto: false,
      buy_budget: null,
    },
  ];

  it('does not render when isOpen is false', () => {
    const { container } = render(
      <SettingsModal
        isOpen={false}
        onClose={vi.fn()}
        settings={initialSettings}
        onSave={vi.fn()}
      />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('renders modal dialog and shows real-time 100% indicator when targets sum to 100%', () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        settings={initialSettings}
        onSave={vi.fn()}
      />
    );

    expect(screen.getByText(/Portfolio Strategy/i)).toBeInTheDocument();
    const hundredEls = screen.getAllByText(/100\.0%/);
    expect(hundredEls.length).toBeGreaterThan(0);
    expect(hundredEls.some((el) => el.className.includes('text-emerald'))).toBe(true);
  });

  it('shows warning and prevents saving when target weights do not sum to 100%', async () => {
    const onSave = vi.fn();
    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        settings={initialSettings}
        onSave={onSave}
      />
    );

    // Find input for VWCE.DE and change to 50 (total becomes 94.5%)
    const vwceInput = screen.getByLabelText(/All-World ETF/i);
    fireEvent.change(vwceInput, { target: { value: '50' } });

    // Expect warning indicator
    expect(screen.getAllByText(/94\.5%/).length).toBeGreaterThan(0);

    const saveBtn = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(saveBtn);

    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByText(/Total must equal 100%/i)).toBeInTheDocument();
  });

  it('allows editing crypto buy dip trigger and sell profit target and saves valid updates', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        settings={initialSettings}
        onSave={onSave}
      />
    );

    // Switch to Crypto Triggers tab
    const cryptoTab = screen.getByRole('button', { name: /Crypto Triggers/i });
    fireEvent.click(cryptoTab);

    // Update BTC buy dip trigger to 60000
    const buyInput = screen.getByLabelText(/Buy Dip Trigger \(BTC-EUR\)/i);
    fireEvent.change(buyInput, { target: { value: '60000' } });

    // Update BTC sell profit target to 80000
    const sellInput = screen.getByLabelText(/Profit Target \(BTC-EUR\)/i);
    fireEvent.change(sellInput, { target: { value: '80000' } });

    // Click save
    const saveBtn = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1);
    });

    const savedPayload: PortfolioAssetSetting[] = onSave.mock.calls[0][0];
    const btc = savedPayload.find((s) => s.symbol === 'BTC-EUR');
    expect(btc?.buy_dip_trigger).toBe(60000);
    expect(btc?.sell_profit_trigger).toBe(80000);
  });

  it('calls onClose when Cancel or Close X is clicked', () => {
    const onClose = vi.fn();
    render(
      <SettingsModal
        isOpen={true}
        onClose={onClose}
        settings={initialSettings}
        onSave={vi.fn()}
      />
    );

    const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelBtn);

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
