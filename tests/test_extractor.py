from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.extract.alphavantage import AlphaVantageExtractor

_FAKE_RESPONSE = {
    "Meta Data": {
        "2. Symbol": "AAPL",
        "3. Last Refreshed": "2024-01-05",
    },
    "Time Series (Daily)": {
        "2024-01-05": {
            "1. open": "185.00",
            "2. high": "187.50",
            "3. low": "184.00",
            "4. close": "186.75",
            "5. volume": "50000000",
        },
        "2024-01-04": {
            "1. open": "182.00",
            "2. high": "185.00",
            "3. low": "181.50",
            "4. close": "184.92",
            "5. volume": "55000000",
        },
        # Outside the requested date range — must be filtered out
        "2023-12-29": {
            "1. open": "193.00",
            "2. high": "194.00",
            "3. low": "191.00",
            "4. close": "192.53",
            "5. volume": "28000000",
        },
    },
}


@patch("src.extract.alphavantage.requests.get")
def test_fetch_prices_filters_date_range(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = _FAKE_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    extractor = AlphaVantageExtractor(api_key="TEST_KEY")
    _, records = extractor.fetch_prices("AAPL", "2024-01-01", "2024-01-31")

    assert len(records) == 2
    assert records[0].trade_date == date(2024, 1, 4)
    assert records[1].trade_date == date(2024, 1, 5)


@patch("src.extract.alphavantage.requests.get")
def test_fetch_prices_maps_ohlcv_correctly(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = _FAKE_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    extractor = AlphaVantageExtractor(api_key="TEST_KEY")
    _, records = extractor.fetch_prices("AAPL", "2024-01-01", "2024-01-31")

    r = records[1]  # 2024-01-05
    assert r.open_price == 185.0
    assert r.high_price == 187.5
    assert r.low_price == 184.0
    assert r.close_price == 186.75
    assert r.volume == 50_000_000


@patch("src.extract.alphavantage.requests.get")
def test_fetch_prices_raises_on_error_message(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"Error Message": "Invalid API call."}
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    extractor = AlphaVantageExtractor(api_key="TEST_KEY")
    with pytest.raises(ValueError, match="rejected symbol"):
        extractor.fetch_prices("INVALID", "2024-01-01", "2024-01-31")


@patch("src.extract.alphavantage.requests.get")
def test_fetch_prices_returns_empty_when_no_data_in_range(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = _FAKE_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    extractor = AlphaVantageExtractor(api_key="TEST_KEY")
    _, records = extractor.fetch_prices("AAPL", "2020-01-01", "2020-01-31")

    assert records == []
