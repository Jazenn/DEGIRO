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

-- Insert default assets
INSERT INTO degiro_assets (product_key, display_name, target_pct, t1_sell, t1_buy, buy_budget) VALUES 
('Ex-USA', 'Ex-USA', 21.0, NULL, NULL, NULL),
('FOD', 'FOD', 5.0, NULL, NULL, NULL),
('All-World', 'All-World', 55.5, NULL, NULL, NULL),
('Europe', 'Europe', 8.5, NULL, NULL, NULL),
('ETHEREUM', 'ETHEREUM', 2.0, NULL, NULL, NULL),
('BITCOIN', 'BITCOIN', 8.0, 75421.59296874999, 66366.21875, 271.8899301198828)
ON CONFLICT (product_key) DO NOTHING;
