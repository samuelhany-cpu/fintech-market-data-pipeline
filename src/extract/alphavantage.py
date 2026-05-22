import logging
from datetime import date

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import settings
from src.extract.base import MarketDataExtractor, PriceRecord

logger = logging.getLogger(__name__)

BASE_URL = "https://www.alphavantage.co/query"
SOURCE_NAME = "alphavantage"


class AlphaVantageExtractor(MarketDataExtractor):
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.alphavantage_api_key
        if not self.api_key:
            raise ValueError("ALPHAVANTAGE_API_KEY is not set in environment or .env")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=30),
        reraise=True,
    )
    def fetch_prices(
        self, symbol: str, start_date: str, end_date: str
    ) -> tuple[dict, list[PriceRecord]]:
        symbol = symbol.upper().strip()
        logger.info(f"Fetching {symbol} from Alpha Vantage ({start_date} -> {end_date})")

        response = requests.get(
            BASE_URL,
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "outputsize": "full",
                "apikey": self.api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        raw: dict = response.json()

        if "Error Message" in raw:
            raise ValueError(f"Alpha Vantage rejected symbol '{symbol}': {raw['Error Message']}")
        if "Note" in raw:
            raise RuntimeError(f"Alpha Vantage rate limit hit: {raw['Note']}")
        if "Information" in raw:
            raise RuntimeError(f"Alpha Vantage API limit: {raw['Information']}")

        time_series: dict = raw.get("Time Series (Daily)", {})
        if not time_series:
            logger.warning(f"Empty time series returned for {symbol}")
            return raw, []

        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        records: list[PriceRecord] = []
        for date_str, values in time_series.items():
            trade_date = date.fromisoformat(date_str)
            if not (start <= trade_date <= end):
                continue
            records.append(
                PriceRecord(
                    symbol=symbol,
                    trade_date=trade_date,
                    open_price=float(values["1. open"]),
                    high_price=float(values["2. high"]),
                    low_price=float(values["3. low"]),
                    close_price=float(values["4. close"]),
                    volume=int(values["5. volume"]),
                )
            )

        records.sort(key=lambda r: r.trade_date)
        logger.info(f"  -> {len(records)} records for {symbol}")
        return raw, records
