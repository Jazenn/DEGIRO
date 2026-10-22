-- ==========================================================================
-- DEGIRO Dashboard — Database Setup
-- ==========================================================================

-- Clean up deprecated JSONB tables
DROP TABLE IF EXISTS degiro_config;
DROP TABLE IF EXISTS degiro_snapshots;

-- --------------------------------------------------------------------------
-- 1. Transacties
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS degiro_transactions (
    id          BIGSERIAL PRIMARY KEY,
    row_hash    TEXT        UNIQUE NOT NULL,   -- MD5 dedup key
    date        DATE,
    time        TEXT,
    value_date  DATE,
    product     TEXT,
    isin        TEXT,
    description TEXT,
    fx          DOUBLE PRECISION DEFAULT 0.0,
    amount      DOUBLE PRECISION DEFAULT 0.0,
    balance     DOUBLE PRECISION DEFAULT 0.0,
    order_id    TEXT,
    csv_row_id  INTEGER,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_degiro_tx_date    ON degiro_transactions (date);
CREATE INDEX IF NOT EXISTS idx_degiro_tx_isin    ON degiro_transactions (isin);
CREATE INDEX IF NOT EXISTS idx_degiro_tx_product ON degiro_transactions (product);


-- --------------------------------------------------------------------------
-- 2. Snapshots (koersen + portfolio geschiedenis)
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS degiro_price_snapshots (
    ticker         TEXT PRIMARY KEY,
    live_price     DOUBLE PRECISION,
    prev_close     DOUBLE PRECISION,
    midnight_price DOUBLE PRECISION,
    market_open    DOUBLE PRECISION,
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

-- history is best kept as JSON due to time-series complexities
CREATE TABLE IF NOT EXISTS degiro_history_snapshots (
    key         TEXT PRIMARY KEY,   -- 'history'
    data        JSONB,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portfolio_daily_history (
    date                    DATE PRIMARY KEY,
    total_equity_eur         DOUBLE PRECISION NOT NULL,
    invested_capital_eur     DOUBLE PRECISION NOT NULL,
    cash_balance_eur         DOUBLE PRECISION NOT NULL,
    unrealized_pnl_eur       DOUBLE PRECISION NOT NULL,
    unrealized_pnl_pct       DOUBLE PRECISION NOT NULL,
    updated_at               TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS current_asset_holdings (
    symbol                  TEXT PRIMARY KEY,
    name                    TEXT NOT NULL,
    isin                    TEXT,
    shares_held             DOUBLE PRECISION NOT NULL,
    current_price_eur       DOUBLE PRECISION NOT NULL,
    total_value_eur         DOUBLE PRECISION NOT NULL,
    total_cost_eur          DOUBLE PRECISION NOT NULL,
    unrealized_pnl_eur      DOUBLE PRECISION NOT NULL,
    actual_pct              DOUBLE PRECISION NOT NULL,
    target_pct              DOUBLE PRECISION NOT NULL,
    drift_pct               DOUBLE PRECISION NOT NULL,
    recommended_action_eur  DOUBLE PRECISION NOT NULL,
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- --------------------------------------------------------------------------
-- 3. Configuratie (portfolio targets, instellingen, ticker mappings)
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS degiro_settings (
    setting_key    TEXT PRIMARY KEY,
    setting_value  TEXT,
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS degiro_assets (
    product_key    TEXT PRIMARY KEY,
    display_name   TEXT,
    target_pct     DOUBLE PRECISION DEFAULT 0.0,
    t1_sell        DOUBLE PRECISION,
    t1_buy         DOUBLE PRECISION,
    buy_budget     DOUBLE PRECISION,
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Strategy rebalancing targets and crypto price execution triggers
CREATE TABLE IF NOT EXISTS portfolio_asset_settings (
    symbol               TEXT PRIMARY KEY,
    display_name         TEXT,
    target_pct           DOUBLE PRECISION DEFAULT 0.0,
    buy_dip_trigger      DOUBLE PRECISION,
    sell_profit_trigger  DOUBLE PRECISION,
    sell_profit_pct      DOUBLE PRECISION DEFAULT 15.0,
    is_crypto            BOOLEAN DEFAULT FALSE,
    buy_budget           DOUBLE PRECISION,
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS degiro_mappings (
    mapping_key    TEXT PRIMARY KEY,
    ticker         TEXT,
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Insert defaults for settings
INSERT INTO degiro_settings (setting_key, setting_value) VALUES 
('stock_fee_eur', '1.0'),
('crypto_fee_pct', '0.29')
ON CONFLICT (setting_key) DO NOTHING;

-- Insert default mappings
INSERT INTO degiro_mappings (mapping_key, ticker) VALUES 
('IE00BK5BQT80', 'VWCE.DE'),
('IE00B4K48X80', 'IMAE.AS'),
('IE0006WW1TQ4', 'EXUS.DE'),
('IE000OJ5TQP4', 'ASWC.DE'),
('XFC000A2YY6Q', 'BTC-EUR'),
('XFC000A2YY6X', 'ETH-EUR'),
('All-World', 'VWCE.DE'),
('Europe', 'IMAE.AS'),
('Ex-USA', 'EXUS.DE'),
('FOD', 'ASWC.DE'),
('BITCOIN', 'BTC-EUR'),
('ETHEREUM', 'ETH-EUR'),
('BMG0112X1056', 'AGN.AS'),
('AEGON LTD', 'AGN.AS')
ON CONFLICT (mapping_key) DO NOTHING;

-- Insert default assets (legacy table)
INSERT INTO degiro_assets (product_key, display_name, target_pct, t1_sell, t1_buy, buy_budget) VALUES 
('Ex-USA', 'Ex-USA', 21.0, NULL, NULL, NULL),
('FOD', 'FOD', 5.0, NULL, NULL, NULL),
('All-World', 'All-World', 55.5, NULL, NULL, NULL),
('Europe', 'Europe', 8.5, NULL, NULL, NULL),
('ETHEREUM', 'ETHEREUM', 2.0, NULL, NULL, NULL),
('BITCOIN', 'BITCOIN', 8.0, 75421.59296874999, 66366.21875, 271.8899301198828)
ON CONFLICT (product_key) DO NOTHING;

-- Insert default portfolio asset settings
INSERT INTO portfolio_asset_settings (symbol, display_name, target_pct, buy_dip_trigger, sell_profit_trigger, is_crypto, buy_budget) VALUES 
('VWCE.DE', 'Vanguard FTSE All-World UCITS ETF', 55.5, NULL, NULL, FALSE, NULL),
('EXUS.DE', 'iShares MSCI World ex-USA UCITS ETF', 21.0, NULL, NULL, FALSE, NULL),
('BTC-EUR', 'Bitcoin', 8.0, 58500.0, 75420.0, TRUE, 350.0),
('IMAE.AS', 'iShares European Property Yield / Small ETF', 8.5, NULL, NULL, FALSE, NULL),
('ASWC.DE', 'Clean Energy & Technology ETF', 5.0, NULL, NULL, FALSE, NULL),
('ETH-EUR', 'Ethereum', 2.0, 2800.0, 3800.0, TRUE, 150.0)
ON CONFLICT (symbol) DO NOTHING;

-- Compatibility synchronization function from portfolio_asset_settings to degiro_assets
CREATE OR REPLACE FUNCTION sync_portfolio_settings_to_degiro_assets()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO degiro_assets (product_key, display_name, target_pct, t1_buy, t1_sell, buy_budget, updated_at)
    VALUES (NEW.symbol, NEW.display_name, NEW.target_pct, NEW.buy_dip_trigger, NEW.sell_profit_trigger, NEW.buy_budget, NOW())
    ON CONFLICT (product_key) DO UPDATE SET
        display_name = EXCLUDED.display_name,
        target_pct = EXCLUDED.target_pct,
        t1_buy = EXCLUDED.t1_buy,
        t1_sell = EXCLUDED.t1_sell,
        buy_budget = EXCLUDED.buy_budget,
        updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_portfolio_asset_settings ON portfolio_asset_settings;
CREATE TRIGGER trg_sync_portfolio_asset_settings
AFTER INSERT OR UPDATE ON portfolio_asset_settings
FOR EACH ROW
EXECUTE FUNCTION sync_portfolio_settings_to_degiro_assets();


-- Preserve normalized identity, currencies, source records and diagnostics.
-- Additive migration: legacy generations remain available for reconciliation.
ALTER TABLE degiro_transactions ADD COLUMN IF NOT EXISTS normalized_record JSONB;
