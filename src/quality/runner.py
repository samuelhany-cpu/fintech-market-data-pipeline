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
    status: str  # "pass" | "fail" | "warning"
    failed_count: int
    details: dict = field(default_factory=dict)


_CHECKS: dict[str, str] = {
    "required_fields": """
        SELECT COUNT(*) FROM stg_market_prices
        WHERE symbol_id IS NULL
           OR trade_date IS NULL
           OR open_price IS NULL
           OR high_price IS NULL
           OR low_price  IS NULL
           OR close_price IS NULL
    """,
    "positive_prices": """
        SELECT COUNT(*) FROM stg_market_prices
        WHERE open_price  <= 0
           OR high_price  <= 0
           OR low_price   <= 0
           OR close_price <= 0
    """,
    "ohlc_consistency": """
        SELECT COUNT(*) FROM stg_market_prices
        WHERE high_price  < low_price
           OR open_price  > high_price
           OR open_price  < low_price
           OR close_price > high_price
           OR close_price < low_price
    """,
    "negative_volume": """
        SELECT COUNT(*) FROM stg_market_prices
        WHERE volume IS NOT NULL AND volume < 0
    """,
    "duplicate_symbol_date": """
        SELECT COUNT(*) FROM (
            SELECT symbol_id, trade_date, COUNT(*) AS cnt
            FROM stg_market_prices
            GROUP BY symbol_id, trade_date
            HAVING COUNT(*) > 1
        ) dupes
    """,
}

_TABLE = "stg_market_prices"


class DataQualityRunner:
    def run_all(self, pipeline_run_id: str) -> list[QualityResult]:
        results: list[QualityResult] = []
        with engine.begin() as conn:
            for check_name, sql in _CHECKS.items():
                failed_count: int = conn.execute(text(sql)).scalar() or 0
                status = "pass" if failed_count == 0 else "fail"
                result = QualityResult(
                    check_name=check_name,
                    table_name=_TABLE,
                    status=status,
                    failed_count=failed_count,
                )
                results.append(result)
                conn.execute(
                    text("""
                        INSERT INTO data_quality_results
                            (pipeline_run_id, check_name, table_name, status, failed_count, details)
                        VALUES
                            (:run_id, :check_name, :table_name, :status, :failed_count, :details::jsonb)
                    """),
                    {
                        "run_id": pipeline_run_id,
                        "check_name": check_name,
                        "table_name": _TABLE,
                        "status": status,
                        "failed_count": failed_count,
                        "details": json.dumps(result.details),
                    },
                )
        return results

    def print_report(self, results: list[QualityResult]) -> None:
        print("\n" + "=" * 55)
        print(f"{'DATA QUALITY REPORT':^55}")
        print("=" * 55)
        print(f"{'Check':<30} {'Status':>8} {'Failed':>10}")
        print("-" * 55)
        all_pass = True
        for r in results:
            icon = "PASS" if r.status == "pass" else "FAIL"
            if r.status != "pass":
                all_pass = False
            print(f"{r.check_name:<30} {icon:>8} {r.failed_count:>10}")
        print("=" * 55)
        overall = "ALL CHECKS PASSED" if all_pass else "SOME CHECKS FAILED"
        print(f"{overall:^55}")
        print("=" * 55 + "\n")
