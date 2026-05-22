import logging

from sqlalchemy import text

from src.db.engine import engine
from src.extract.base import PriceRecord

logger = logging.getLogger(__name__)


def upsert_symbol(symbol: str) -> int:
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO symbols (symbol)
                VALUES (:symbol)
                ON CONFLICT (symbol) DO UPDATE SET symbol = EXCLUDED.symbol
                RETURNING id
            """),
            {"symbol": symbol.upper().strip()},
        )
        return result.fetchone()[0]


def upsert_staging(symbol_id: int, records: list[PriceRecord], source_name: str) -> int:
    if not records:
        return 0
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO stg_market_prices
                    (symbol_id, trade_date, open_price, high_price, low_price,
                     close_price, volume, source_name)
                VALUES
                    (:symbol_id, :trade_date, :open_price, :high_price, :low_price,
                     :close_price, :volume, :source_name)
                ON CONFLICT (symbol_id, trade_date)
                DO UPDATE SET
                    open_price  = EXCLUDED.open_price,
                    high_price  = EXCLUDED.high_price,
                    low_price   = EXCLUDED.low_price,
                    close_price = EXCLUDED.close_price,
                    volume      = EXCLUDED.volume,
                    source_name = EXCLUDED.source_name,
                    loaded_at   = NOW()
            """),
            [
                {
                    "symbol_id": symbol_id,
                    "trade_date": r.trade_date,
                    "open_price": r.open_price,
                    "high_price": r.high_price,
                    "low_price": r.low_price,
                    "close_price": r.close_price,
                    "volume": r.volume,
                    "source_name": source_name,
                }
                for r in records
            ],
        )
    logger.info(f"[staging_loader] Upserted {len(records)} rows for symbol_id={symbol_id}")
    return len(records)


def get_latest_trade_date(symbol_id: int) -> str | None:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT MAX(trade_date) FROM stg_market_prices WHERE symbol_id = :sid"),
            {"sid": symbol_id},
        )
        row = result.fetchone()
        return str(row[0]) if row and row[0] else None
