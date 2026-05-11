-- ==========================================================================
-- DEGIRO Dashboard — Database Setup
-- ==========================================================================
-- Voer dit eenmalig uit in de SQL editor van jouw database provider
-- (Neon: Dashboard → SQL Editor, of via psql).
--
-- Alle tabellen hebben een 'degiro_' prefix zodat ze veilig naast andere
-- projecten in dezelfde database kunnen staan.
-- ==========================================================================


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

-- Index voor snelle lookups op datum en product
CREATE INDEX IF NOT EXISTS idx_degiro_tx_date    ON degiro_transactions (date);
CREATE INDEX IF NOT EXISTS idx_degiro_tx_isin    ON degiro_transactions (isin);
CREATE INDEX IF NOT EXISTS idx_degiro_tx_product ON degiro_transactions (product);


-- --------------------------------------------------------------------------
-- 2. Snapshots (koersen + portfolio geschiedenis)
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS degiro_snapshots (
    key         TEXT PRIMARY KEY,   -- 'prices' of 'history'
    data        JSONB,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);


-- --------------------------------------------------------------------------
-- 3. Configuratie (portfolio targets, instellingen, ticker mappings)
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS degiro_config (
    key         TEXT PRIMARY KEY,   -- 'target_config'
    value       JSONB,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);


-- ==========================================================================
-- Eenmalige data migratie: target_config.json
-- Pas de JSON hieronder aan als je configuratie afwijkt.
-- ==========================================================================
INSERT INTO degiro_config (key, value) VALUES (
    'target_config',
    '{
      "assets": {
        "Ex-USA":    {"target_pct": 21.0,  "display_name": "Ex-USA"},
        "FOD":       {"target_pct": 5.0,   "display_name": "FOD"},
        "All-World": {"target_pct": 55.5,  "display_name": "All-World"},
        "Europe":    {"target_pct": 8.5,   "display_name": "Europe"},
        "ETHEREUM":  {"target_pct": 2.0,   "display_name": "ETHEREUM"},
        "BITCOIN":   {
          "target_pct": 8.0,
          "display_name": "BITCOIN",
          "trading_strategy": {
            "t1_sell": 75421.59296874999,
            "t1_buy":  66366.21875,
            "buy_budget": 271.8899301198828
          }
        }
      },
      "settings": {
        "stock_fee_eur": 1.0,
        "crypto_fee_pct": 0.29
      },
      "mappings": {
        "IE00BK5BQT80": "VWCE.DE",
        "IE00B4K48X80": "IMAE.AS",
        "IE0006WW1TQ4": "EXUS.DE",
        "IE000OJ5TQP4": "ASWC.DE",
        "XFC000A2YY6Q": "BTC-EUR",
        "XFC000A2YY6X": "ETH-EUR",
        "All-World":    "VWCE.DE",
        "Europe":       "IMAE.AS",
        "Ex-USA":       "EXUS.DE",
        "FOD":          "ASWC.DE",
        "BITCOIN":      "BTC-EUR",
        "ETHEREUM":     "ETH-EUR",
        "BMG0112X1056": "AGN.AS",
        "AEGON LTD":    "AGN.AS"
      }
    }'::jsonb
) ON CONFLICT (key) DO NOTHING;
