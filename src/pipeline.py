"""
Main pipeline orchestrator.

Usage:
    python -m src.pipeline --symbols AAPL MSFT TSLA --start 2024-01-01 --end 2024-12-31
"""

import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import text

from src.db.engine import engine
from src.db.init_db import init_db
from src.extract.alphavantage import AlphaVantageExtractor
from src.load.raw_loader import load_raw_payload
from src.load.staging_loader import upsert_staging, upsert_symbol
from src.quality.runner import DataQualityRunner
from src.transform.mart_builder import build_mart

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

SOURCE_NAME = "alphavantage"
# Alpha Vantage free tier: 5 requests/minute -> pause 13s between requests.
_API_DELAY_SECONDS = 13


def _create_pipeline_run(pipeline_name: str) -> str:
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO pipeline_runs (pipeline_name, status)
                VALUES (:name, 'running')
                RETURNING id
            """),
            {"name": pipeline_name},
        )
        run_id = str(result.fetchone()[0])
    logger.info(f"[pipeline] Created run {run_id}")
    return run_id


def _finish_pipeline_run(run_id: str, status: str, error: str | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE pipeline_runs
                SET status = :status, finished_at = NOW(), error_message = :error
                WHERE id = :run_id
            """),
            {"run_id": run_id, "status": status, "error": error},
        )


def _ingest_symbol(
    extractor: AlphaVantageExtractor,
    symbol: str,
    start_date: str,
    end_date: str,
    pipeline_run_id: str,
) -> int:
    symbol_id = upsert_symbol(symbol)
    raw_payload, records = extractor.fetch_prices(symbol, start_date, end_date)
    if records:
        load_raw_payload(symbol_id, pipeline_run_id, SOURCE_NAME, start_date, end_date, raw_payload)
        return upsert_staging(symbol_id, records, SOURCE_NAME)
    logger.warning(f"[pipeline] No records for {symbol} in range {start_date} -> {end_date}")
    return 0


def run_pipeline(symbols: list[str], start_date: str, end_date: str) -> None:
    init_db()
    run_id = _create_pipeline_run("market_data_ingest")
    total_rows = 0
    errors: list[str] = []

    extractor = AlphaVantageExtractor()

    # Concurrent extraction with rate-limit delay between submit calls.
    # DB writes are safe: upsert handles conflicts and each symbol occupies distinct rows.
    with ThreadPoolExecutor(max_workers=min(len(symbols), 3)) as pool:
        futures = {}
        for i, symbol in enumerate(symbols):
            if i > 0:
                time.sleep(_API_DELAY_SECONDS)
            future = pool.submit(_ingest_symbol, extractor, symbol, start_date, end_date, run_id)
            futures[future] = symbol

        for future in as_completed(futures):
            symbol = futures[future]
            try:
                rows = future.result()
                total_rows += rows
                logger.info(f"[pipeline] {symbol}: {rows} rows ingested")
            except Exception as exc:
                msg = f"{symbol} failed: {exc}"
                logger.error(f"[pipeline] {msg}")
                errors.append(msg)

    if errors and total_rows == 0:
        _finish_pipeline_run(run_id, "failed", "; ".join(errors))
        print(f"\n[pipeline] Run {run_id} FAILED. Errors: {errors}")
        sys.exit(1)

    logger.info("[pipeline] Running data quality checks...")
    qr = DataQualityRunner()
    quality_results = qr.run_all(run_id)
    qr.print_report(quality_results)

    if any(r.status == "fail" for r in quality_results):
        _finish_pipeline_run(run_id, "failed", "Data quality checks failed")
        sys.exit(1)

    logger.info("[pipeline] Building analytics mart...")
    mart_rows = build_mart()

    _finish_pipeline_run(run_id, "success")
    print(
        f"\n[pipeline] Run {run_id} SUCCESS"
        f" — {total_rows} rows staged, {mart_rows} mart rows built."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fintech Market Data Pipeline")
    parser.add_argument("--symbols", nargs="+", required=True, help="Ticker symbols e.g. AAPL MSFT")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    args = parser.parse_args()
    run_pipeline(
        symbols=[s.upper() for s in args.symbols],
        start_date=args.start,
        end_date=args.end,
    )


if __name__ == "__main__":
    main()
