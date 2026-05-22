from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from src.extract.yfinance_extractor import YFinanceExtractor


def _make_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df.pop("Date"))
    df.index.name = "Date"
    return df


_FAKE_DF = _make_df([
    {"Date": "2024-01-04", "Open": 182.0, "High": 185.0, "Low": 181.5, "Close": 184.92, "Volume": 55_000_000},
    {"Date": "2024-01-05", "Open": 185.0, "High": 187.5, "Low": 184.0, "Close": 186.75, "Volume": 50_000_000},
])


@patch("src.extract.yfinance_extractor.yf.Ticker")
def test_fetch_prices_returns_correct_record_count(mock_ticker):
    mock_ticker.return_value.history.return_value = _FAKE_DF

    extractor = YFinanceExtractor()
    _, records = extractor.fetch_prices("AAPL", "2024-01-01", "2024-01-31")

    assert len(records) == 2


@patch("src.extract.yfinance_extractor.yf.Ticker")
def test_fetch_prices_maps_ohlcv_correctly(mock_ticker):
    mock_ticker.return_value.history.return_value = _FAKE_DF

    extractor = YFinanceExtractor()
    _, records = extractor.fetch_prices("AAPL", "2024-01-01", "2024-01-31")

    r = records[1]  # 2024-01-05
    assert r.trade_date == date(2024, 1, 5)
    assert r.open_price == 185.0
    assert r.high_price == 187.5
    assert r.low_price == 184.0
    assert r.close_price == 186.75
    assert r.volume == 50_000_000


@patch("src.extract.yfinance_extractor.yf.Ticker")
def test_fetch_prices_returns_empty_on_no_data(mock_ticker):
    mock_ticker.return_value.history.return_value = pd.DataFrame()

    extractor = YFinanceExtractor()
    payload, records = extractor.fetch_prices("AAPL", "2024-01-01", "2024-01-31")

    assert records == []
    assert payload["rows"] == 0


@patch("src.extract.yfinance_extractor.yf.Ticker")
def test_fetch_prices_upcases_symbol(mock_ticker):
    mock_ticker.return_value.history.return_value = _FAKE_DF

    extractor = YFinanceExtractor()
    _, records = extractor.fetch_prices("aapl", "2024-01-01", "2024-01-31")

    assert all(r.symbol == "AAPL" for r in records)


@patch("src.extract.yfinance_extractor.yf.Ticker")
def test_fetch_prices_raw_payload_contains_metadata(mock_ticker):
    mock_ticker.return_value.history.return_value = _FAKE_DF

    extractor = YFinanceExtractor()
    payload, _ = extractor.fetch_prices("AAPL", "2024-01-01", "2024-01-31")

    assert payload["source"] == "yfinance"
    assert payload["symbol"] == "AAPL"
    assert payload["rows"] == 2
