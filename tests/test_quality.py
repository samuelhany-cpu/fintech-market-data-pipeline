from src.quality.runner import DataQualityRunner, QualityResult


def test_quality_result_defaults():
    r = QualityResult(
        check_name="null_required_fields",
        table_name="stg_market_prices",
        status="pass",
        failed_count=0,
    )
    assert r.details == {}
    assert r.status == "pass"
    assert r.failed_count == 0


def test_quality_result_warning_status():
    r = QualityResult(
        check_name="zero_volume",
        table_name="stg_market_prices",
        status="warning",
        failed_count=2,
        details={"samples": [{"symbol": "AAPL", "trade_date": "2024-06-01"}]},
    )
    assert r.status == "warning"
    assert r.failed_count == 2
    assert "samples" in r.details


def test_print_report_all_pass(capsys):
    results = [
        QualityResult("null_required_fields",  "stg_market_prices",          "pass", 0),
        QualityResult("non_positive_prices",   "stg_market_prices",          "pass", 0),
        QualityResult("ohlc_ordering",         "stg_market_prices",          "pass", 0),
        QualityResult("duplicate_symbol_date", "stg_market_prices",          "pass", 0),
        QualityResult("negative_volume",       "stg_market_prices",          "pass", 0),
        QualityResult("zero_volume",           "stg_market_prices",          "pass", 0),
        QualityResult("weekend_trade_dates",   "stg_market_prices",          "pass", 0),
        QualityResult("future_trade_dates",    "stg_market_prices",          "pass", 0),
        QualityResult("data_freshness",        "stg_market_prices",          "pass", 2),
        QualityResult("price_spike_detection", "stg_market_prices",          "pass", 0),
        QualityResult("mart_symbol_coverage",  "mart_daily_symbol_metrics",  "pass", 0),
        QualityResult("mart_data_lag",         "mart_daily_symbol_metrics",  "pass", 0),
    ]
    DataQualityRunner().print_report(results)
    captured = capsys.readouterr()
    assert "12 passed" in captured.out
    assert "FAIL" not in captured.out


def test_print_report_with_failure(capsys):
    results = [
        QualityResult("null_required_fields", "stg_market_prices", "pass", 0),
        QualityResult("non_positive_prices",  "stg_market_prices", "fail", 3),
    ]
    DataQualityRunner().print_report(results)
    captured = capsys.readouterr()
    assert "FAIL" in captured.out
    assert "1 failed" in captured.out


def test_print_report_with_warning(capsys):
    results = [
        QualityResult("null_required_fields",  "stg_market_prices", "pass",    0),
        QualityResult("zero_volume",           "stg_market_prices", "warning", 1),
        QualityResult("price_spike_detection", "stg_market_prices", "warning", 4),
    ]
    DataQualityRunner().print_report(results)
    captured = capsys.readouterr()
    assert "WARN" in captured.out
    assert "2 warnings" in captured.out
    assert "FAIL" not in captured.out


def test_freshness_result_reflects_days():
    r = QualityResult(
        check_name="data_freshness",
        table_name="stg_market_prices",
        status="fail",
        failed_count=12,
        details={"max_trade_date": "2024-01-01", "days_since_last_row": 12},
    )
    assert r.status == "fail"
    assert r.failed_count == 12
    assert r.details["days_since_last_row"] == 12
