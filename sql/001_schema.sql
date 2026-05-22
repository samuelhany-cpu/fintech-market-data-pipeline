CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS symbols (
    id          SERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL UNIQUE,
    name        TEXT,
    exchange    TEXT,
    asset_type  TEXT DEFAULT 'equity',
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pipeline_name   TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    started_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMP,
    error_message   TEXT
);

CREATE TABLE IF NOT EXISTS raw_market_payloads (
    id              BIGSERIAL PRIMARY KEY,
    symbol_id       INT NOT NULL REFERENCES symbols(id),
    pipeline_run_id UUID REFERENCES pipeline_runs(id),
    source_name     TEXT NOT NULL,
    from_date       DATE NOT NULL,
    to_date         DATE NOT NULL,
    payload         JSONB NOT NULL,
    ingested_at     TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stg_market_prices (
    id          BIGSERIAL PRIMARY KEY,
    symbol_id   INT NOT NULL REFERENCES symbols(id),
    trade_date  DATE NOT NULL,
    open_price  NUMERIC(18, 6) NOT NULL,
    high_price  NUMERIC(18, 6) NOT NULL,
    low_price   NUMERIC(18, 6) NOT NULL,
    close_price NUMERIC(18, 6) NOT NULL,
    volume      BIGINT,
    source_name TEXT NOT NULL,
    loaded_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (symbol_id, trade_date)
);

CREATE TABLE IF NOT EXISTS mart_daily_symbol_metrics (
    id                    BIGSERIAL PRIMARY KEY,
    symbol_id             INT NOT NULL REFERENCES symbols(id),
    trade_date            DATE NOT NULL,
    close_price           NUMERIC(18, 6) NOT NULL,
    daily_return          NUMERIC(18, 8),
    ma_7                  NUMERIC(18, 6),
    ma_30                 NUMERIC(18, 6),
    rolling_volatility_30 NUMERIC(18, 8),
    volume                BIGINT,
    volume_change         NUMERIC(18, 8),
    built_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (symbol_id, trade_date)
);

CREATE TABLE IF NOT EXISTS data_quality_results (
    id              BIGSERIAL PRIMARY KEY,
    pipeline_run_id UUID REFERENCES pipeline_runs(id),
    check_name      TEXT NOT NULL,
    table_name      TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('pass', 'fail', 'warning')),
    failed_count    INT NOT NULL DEFAULT 0,
    details         JSONB,
    checked_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
