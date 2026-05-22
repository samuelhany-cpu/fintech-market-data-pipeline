from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class PriceRecord:
    symbol: str
    trade_date: date
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int | None


class MarketDataExtractor(ABC):
    @abstractmethod
    def fetch_prices(
        self, symbol: str, start_date: str, end_date: str
    ) -> tuple[dict, list[PriceRecord]]:
        """Return (raw_payload, normalized_records) for the given date range."""
        ...
