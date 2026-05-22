import logging

from sqlalchemy import text

from src.db.engine import engine

logger = logging.getLogger(__name__)

_BUILD_MART_SQL = """
INSERT INTO mart_daily_symbol_metrics (
    symbol_id, trade_date, close_price,
    daily_return, ma_7, ma_30, rolling_volatility_30,
    volume, volume_change
)
SELECT
    symbol_id,
    trade_date,
    close_price,
    (close_price - LAG(close_price) OVER w)
        / NULLIF(LAG(close_price) OVER w, 0)                                        AS daily_return,
    AVG(close_price) OVER (
        PARTITION BY symbol_id ORDER BY trade_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)                                   AS ma_7,
    AVG(close_price) OVER (
        PARTITION BY symbol_id ORDER BY trade_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)                                  AS ma_30,
    STDDEV(close_price) OVER (
        PARTITION BY symbol_id ORDER BY trade_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)                                  AS rolling_volatility_30,
    volume,
    (volume::NUMERIC - LAG(volume) OVER w)
        / NULLIF(LAG(volume) OVER w, 0)                                             AS volume_change
FROM stg_market_prices
WINDOW w AS (PARTITION BY symbol_id ORDER BY trade_date)
ON CONFLICT (symbol_id, trade_date)
DO UPDATE SET
    close_price           = EXCLUDED.close_price,
    daily_return          = EXCLUDED.daily_return,
    ma_7                  = EXCLUDED.ma_7,
    ma_30                 = EXCLUDED.ma_30,
    rolling_volatility_30 = EXCLUDED.rolling_volatility_30,
    volume                = EXCLUDED.volume,
    volume_change         = EXCLUDED.volume_change,
    built_at              = NOW()
"""


def build_mart() -> int:
    with engine.begin() as conn:
        result = conn.execute(text(_BUILD_MART_SQL))
    row_count = result.rowcount
    logger.info(f"[mart_builder] Built/refreshed {row_count} rows in mart_daily_symbol_metrics")
    return row_count
