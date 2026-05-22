from datetime import date

from src.extract.base import PriceRecord


def make_record(
    symbol: str = "AAPL",
    trade_date: date = date(2024, 1, 2),
    open_price: float = 185.0,
    high_price: float = 187.0,
    low_price: float = 184.0,
    close_price: float = 186.0,
    volume: int = 1_000_000,
) -> PriceRecord:
    return PriceRecord(
        symbol=symbol,
        trade_date=trade_date,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=volume,
    )
