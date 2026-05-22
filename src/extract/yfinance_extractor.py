import logging

import yfinance as yf

from src.extract.base import MarketDataExtractor, PriceRecord

logger = logging.getLogger(__name__)

SOURCE_NAME = "yfinance"


class YFinanceExtractor(MarketDataExtractor):
    def fetch_prices(
        self, symbol: str, start_date: str, end_date: str
    ) -> tuple[dict, list[PriceRecord]]:
        symbol = symbol.upper().strip()
        logger.info(f"Fetching {symbol} from yfinance ({start_date} -> {end_date})")

        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date, auto_adjust=True)

        if df.empty:
            logger.warning(f"No data returned for {symbol}")
            return {"source": SOURCE_NAME, "symbol": symbol, "rows": 0}, []

        records: list[PriceRecord] = []
        for ts, row in df.iterrows():
            records.append(
                PriceRecord(
                    symbol=symbol,
                    trade_date=ts.date(),
                    open_price=float(row["Open"]),
                    high_price=float(row["High"]),
                    low_price=float(row["Low"]),
                    close_price=float(row["Close"]),
                    volume=int(row["Volume"]),
                )
            )

        raw_payload = {
            "source": SOURCE_NAME,
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "rows": len(records),
        }
        logger.info(f"  -> {len(records)} records for {symbol}")
        return raw_payload, records
