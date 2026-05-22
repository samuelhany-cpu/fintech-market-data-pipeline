from src.quality.runner import DataQualityRunner, QualityResult, _CHECKS


def test_quality_result_defaults():
    r = QualityResult(
        check_name="positive_prices",
        table_name="stg_market_prices",
        status="pass",
        failed_count=0,
    )
    assert r.details == {}
    assert r.status == "pass"
    assert r.failed_count == 0


def test_all_check_names_present():
    expected = {
        "required_fields",
        "positive_prices",
        "ohlc_consistency",
        "negative_volume",
        "duplicate_symbol_date",
    }
    assert set(_CHECKS.keys()) == expected


def test_each_check_is_a_select_count_query():
    for name, sql in _CHECKS.items():
        normalized = sql.strip().upper()
        assert normalized.startswith("SELECT COUNT(*)"), (
            f"Check '{name}' must start with SELECT COUNT(*)"
        )


def test_print_report_all_pass(capsys):
    results = [
        QualityResult("required_fields", "stg_market_prices", "pass", 0),
        QualityResult("positive_prices", "stg_market_prices", "pass", 0),
        QualityResult("ohlc_consistency", "stg_market_prices", "pass", 0),
        QualityResult("negative_volume", "stg_market_prices", "pass", 0),
        QualityResult("duplicate_symbol_date", "stg_market_prices", "pass", 0),
    ]
    DataQualityRunner().print_report(results)
    captured = capsys.readouterr()
    assert "ALL CHECKS PASSED" in captured.out
    assert "FAIL" not in captured.out


def test_print_report_with_failure(capsys):
    results = [
        QualityResult("required_fields", "stg_market_prices", "pass", 0),
        QualityResult("positive_prices", "stg_market_prices", "fail", 3),
    ]
    DataQualityRunner().print_report(results)
    captured = capsys.readouterr()
    assert "SOME CHECKS FAILED" in captured.out
    assert "FAIL" in captured.out
