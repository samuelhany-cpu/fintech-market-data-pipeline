CREATE INDEX IF NOT EXISTS idx_stg_prices_symbol_date
    ON stg_market_prices (symbol_id, trade_date);

CREATE INDEX IF NOT EXISTS idx_stg_prices_trade_date
    ON stg_market_prices (trade_date);

CREATE INDEX IF NOT EXISTS idx_raw_payloads_symbol_ingested
    ON raw_market_payloads (symbol_id, ingested_at DESC);

CREATE INDEX IF NOT EXISTS idx_mart_metrics_symbol_date
    ON mart_daily_symbol_metrics (symbol_id, trade_date);

CREATE INDEX IF NOT EXISTS idx_quality_pipeline_run
    ON data_quality_results (pipeline_run_id);
