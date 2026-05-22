import json
import logging

from sqlalchemy import text

from src.db.engine import engine

logger = logging.getLogger(__name__)


def load_raw_payload(
    symbol_id: int,
    pipeline_run_id: str,
    source_name: str,
    from_date: str,
    to_date: str,
    payload: dict,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO raw_market_payloads
                    (symbol_id, pipeline_run_id, source_name, from_date, to_date, payload)
                VALUES
                    (:symbol_id, :pipeline_run_id, :source_name, :from_date, :to_date, :payload::jsonb)
            """),
            {
                "symbol_id": symbol_id,
                "pipeline_run_id": pipeline_run_id,
                "source_name": source_name,
                "from_date": from_date,
                "to_date": to_date,
                "payload": json.dumps(payload),
            },
        )
    logger.info(f"[raw_loader] Stored raw payload for symbol_id={symbol_id}")
