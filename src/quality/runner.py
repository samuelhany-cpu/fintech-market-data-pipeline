import json
import logging
from dataclasses import dataclass, field

from sqlalchemy import text

from src.db.engine import engine

logger = logging.getLogger(__name__)


@dataclass
class QualityResult:
    check_name: str
    table_name: str
    status: str          # "pass" | "warning" | "fail"
    failed_count: int
    details: dict = field(default_factory=dict)


def _run_checks(conn) -> list[QualityResult]:
    results: list[QualityResult] = []

    def _check(name: str, table: str, sql: str, *,
               warn_at: int | None = None,
               fail_at: int = 1,
               detail_sql: str | None = None) -> QualityResult:
        count = conn.execute(text(sql)).scalar() or 0
        if fail_at is not None and count >= fail_at:
            status = "fail"
        elif warn_at is not None and count >= warn_at:
            status = "warning"
        else:
            status = "pass"
        details: dict = {}
        if detail_sql and count > 0:
            rows = conn.execute(text(detail_sql)).fetchall()
            details["samples"] = [dict(r._mapping) for r in rows[:10]]
        return QualityResult(check_name=name, table_name=table,
                             status=status, failed_count=count, details=details)

    # ── 1. NULL in critical columns ────────────────────────────────────────
    results.append(_check(
        "null_required_fields", "stg_market_prices",
        """
        SELECT COUNT(*) FROM stg_market_prices
        WHERE symbol_id IS NULL OR trade_date IS NULL
           OR open_price IS NULL OR high_price IS NULL
           OR low_price  IS NULL OR close_price IS NULL
        """,
    ))

    # ── 2. Prices ≤ 0 ─────────────────────────────────────────────────────
    results.append(_check(
        "non_positive_prices", "stg_market_prices",
        """
        SELECT COUNT(*) FROM stg_market_prices
        WHERE open_price <= 0 OR high_price <= 0
           OR low_price  <= 0 OR close_price <= 0
        """,
        detail_sql="""
        SELECT s.symbol, p.trade_date, p.open_price, p.high_price,
               p.low_price, p.close_price
        FROM stg_market_prices p
        JOIN symbols s ON s.id = p.symbol_id
        WHERE p.open_price <= 0 OR p.high_price <= 0
           OR p.low_price  <= 0 OR p.close_price <= 0
        ORDER BY p.trade_date DESC LIMIT 10
        """,
    ))

    # ── 3. OHLC ordering constraint ────────────────────────────────────────
    results.append(_check(
        "ohlc_ordering", "stg_market_prices",
        """
        SELECT COUNT(*) FROM stg_market_prices
        WHERE high_price  < low_price
           OR open_price  > high_price
           OR open_price  < low_price
           OR close_price > high_price
           OR close_price < low_price
        """,
        detail_sql="""
        SELECT s.symbol, p.trade_date,
               p.open_price, p.high_price, p.low_price, p.close_price
        FROM stg_market_prices p
        JOIN symbols s ON s.id = p.symbol_id
        WHERE p.high_price  < p.low_price
           OR p.open_price  > p.high_price
           OR p.open_price  < p.low_price
           OR p.close_price > p.high_price
           OR p.close_price < p.low_price
        ORDER BY p.trade_date DESC LIMIT 10
        """,
    ))

    # ── 4. Duplicate (symbol, trade_date) ─────────────────────────────────
    results.append(_check(
        "duplicate_symbol_date", "stg_market_prices",
        """
        SELECT COUNT(*) FROM (
            SELECT symbol_id, trade_date
            FROM stg_market_prices
            GROUP BY symbol_id, trade_date
            HAVING COUNT(*) > 1
        ) d
        """,
    ))

    # ── 5. Negative volume ─────────────────────────────────────────────────
    results.append(_check(
        "negative_volume", "stg_market_prices",
        """
        SELECT COUNT(*) FROM stg_market_prices
        WHERE volume IS NOT NULL AND volume < 0
        """,
    ))

    # ── 6. Zero volume — warn only; zero traded volume is suspicious ───────
    results.append(_check(
        "zero_volume", "stg_market_prices",
        """
        SELECT COUNT(*) FROM stg_market_prices
        WHERE volume = 0
        """,
        warn_at=1, fail_at=None,
        detail_sql="""
        SELECT s.symbol, p.trade_date
        FROM stg_market_prices p
        JOIN symbols s ON s.id = p.symbol_id
        WHERE p.volume = 0
        ORDER BY p.trade_date DESC LIMIT 10
        """,
    ))

    # ── 7. Weekend dates (equities don't trade Sat/Sun) ───────────────────
    results.append(_check(
        "weekend_trade_dates", "stg_market_prices",
        """
        SELECT COUNT(*) FROM stg_market_prices
        WHERE EXTRACT(DOW FROM trade_date) IN (0, 6)
        """,
        detail_sql="""
        SELECT s.symbol, p.trade_date,
               TO_CHAR(p.trade_date, 'Day') AS day_of_week
        FROM stg_market_prices p
        JOIN symbols s ON s.id = p.symbol_id
        WHERE EXTRACT(DOW FROM p.trade_date) IN (0, 6)
        ORDER BY p.trade_date DESC LIMIT 10
        """,
    ))

    # ── 8. Future dates ────────────────────────────────────────────────────
    results.append(_check(
        "future_trade_dates", "stg_market_prices",
        """
        SELECT COUNT(*) FROM stg_market_prices
        WHERE trade_date > CURRENT_DATE
        """,
        detail_sql="""
        SELECT s.symbol, p.trade_date
        FROM stg_market_prices p
        JOIN symbols s ON s.id = p.symbol_id
        WHERE p.trade_date > CURRENT_DATE
        ORDER BY p.trade_date DESC LIMIT 10
        """,
    ))

    # ── 9. Data freshness — warn if >5 days stale, fail if >10 days ───────
    stale_row = conn.execute(text("""
        SELECT
            MAX(trade_date)                           AS max_date,
            (CURRENT_DATE - MAX(trade_date))::int     AS days_old
        FROM stg_market_prices
    """)).fetchone()

    if stale_row and stale_row.max_date is not None:
        days_old = stale_row.days_old or 0
        if days_old >= 10:
            stale_status = "fail"
        elif days_old >= 5:
            stale_status = "warning"
        else:
            stale_status = "pass"
        results.append(QualityResult(
            check_name="data_freshness",
            table_name="stg_market_prices",
            status=stale_status,
            failed_count=days_old,
            details={
                "max_trade_date": str(stale_row.max_date),
                "days_since_last_row": days_old,
            },
        ))
    else:
        results.append(QualityResult(
            check_name="data_freshness",
            table_name="stg_market_prices",
            status="fail",
            failed_count=0,
            details={"error": "no rows in stg_market_prices"},
        ))

    # ── 10. Price-spike detection — single-day close return > 40% ─────────
    #    Uses LAG window function; flagged as warning (may be a real event)
    results.append(_check(
        "price_spike_detection", "stg_market_prices",
        """
        SELECT COUNT(*) FROM (
            SELECT
                ABS(
                    (close_price - LAG(close_price) OVER w)
                    / NULLIF(LAG(close_price) OVER w, 0)
                ) AS ret
            FROM stg_market_prices
            WINDOW w AS (PARTITION BY symbol_id ORDER BY trade_date)
        ) sub
        WHERE ret > 0.40
        """,
        warn_at=1, fail_at=None,
        detail_sql="""
        SELECT s.symbol, p.trade_date,
               ROUND(
                   (p.close_price - LAG(p.close_price) OVER w)
                   / NULLIF(LAG(p.close_price) OVER w, 0) * 100, 2
               ) AS pct_change,
               p.close_price
        FROM stg_market_prices p
        JOIN symbols s ON s.id = p.symbol_id
        WINDOW w AS (PARTITION BY p.symbol_id ORDER BY p.trade_date)
        ORDER BY ABS(pct_change) DESC NULLS LAST
        LIMIT 10
        """,
    ))

    # ── 11. Mart symbol coverage — symbols in stg missing from mart ────────
    results.append(_check(
        "mart_symbol_coverage", "mart_daily_symbol_metrics",
        """
        SELECT COUNT(DISTINCT symbol_id) FROM stg_market_prices
        WHERE symbol_id NOT IN (
            SELECT DISTINCT symbol_id FROM mart_daily_symbol_metrics
        )
        """,
        detail_sql="""
        SELECT s.symbol FROM symbols s
        WHERE s.id IN (SELECT DISTINCT symbol_id FROM stg_market_prices)
          AND s.id NOT IN (SELECT DISTINCT symbol_id FROM mart_daily_symbol_metrics)
        """,
    ))

    # ── 12. Mart freshness — mart lagging behind staging ──────────────────
    lag_row = conn.execute(text("""
        SELECT
            (SELECT MAX(trade_date) FROM stg_market_prices)         AS stg_max,
            (SELECT MAX(trade_date) FROM mart_daily_symbol_metrics) AS mart_max
    """)).fetchone()

    if lag_row and lag_row.stg_max and lag_row.mart_max:
        lag_days = (lag_row.stg_max - lag_row.mart_max).days
        results.append(QualityResult(
            check_name="mart_data_lag",
            table_name="mart_daily_symbol_metrics",
            status="fail" if lag_days > 1 else "pass",
            failed_count=lag_days,
            details={
                "stg_max_date": str(lag_row.stg_max),
                "mart_max_date": str(lag_row.mart_max),
                "lag_days": lag_days,
            },
        ))
    else:
        results.append(QualityResult(
            check_name="mart_data_lag",
            table_name="mart_daily_symbol_metrics",
            status="warning" if (lag_row and lag_row.stg_max) else "pass",
            failed_count=0,
            details={"note": "mart table is empty"},
        ))

    return results


class DataQualityRunner:
    def run_all(self, pipeline_run_id: str) -> list[QualityResult]:
        results: list[QualityResult] = []
        with engine.begin() as conn:
            results = _run_checks(conn)
            for r in results:
                conn.execute(
                    text("""
                        INSERT INTO data_quality_results
                            (pipeline_run_id, check_name, table_name,
                             status, failed_count, details)
                        VALUES
                            (:run_id, :check_name, :table_name,
                             :status, :failed_count, cast(:details as jsonb))
                    """),
                    {
                        "run_id": pipeline_run_id,
                        "check_name": r.check_name,
                        "table_name": r.table_name,
                        "status": r.status,
                        "failed_count": r.failed_count,
                        "details": json.dumps(r.details, default=str),
                    },
                )
        return results

    def print_report(self, results: list[QualityResult]) -> None:
        width = 70
        print("\n" + "=" * width)
        print(f"{'DATA QUALITY REPORT':^{width}}")
        print("=" * width)
        print(f"{'Check':<35} {'Table':<22} {'Status':>7} {'Count':>7}")
        print("-" * width)
        counts: dict[str, int] = {"pass": 0, "warning": 0, "fail": 0}
        for r in results:
            counts[r.status] = counts.get(r.status, 0) + 1
            tag = {"pass": "PASS", "warning": "WARN", "fail": "FAIL"}[r.status]
            print(f"{r.check_name:<35} {r.table_name:<22} {tag:>7} {r.failed_count:>7}")
            if r.details and r.status != "pass":
                for k, v in r.details.items():
                    if k != "samples":
                        print(f"  {'':35} {k}: {v}")
        print("=" * width)
        summary = (
            f"  {counts['pass']} passed  |  "
            f"{counts['warning']} warnings  |  "
            f"{counts['fail']} failed"
        )
        print(f"{summary:^{width}}")
        print("=" * width + "\n")
