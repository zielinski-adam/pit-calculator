"""Mapowanie giełd IBKR → exchange_calendars i cykle rozrachunkowe."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class ListingExchange(StrEnum):
    """Kody giełd z IBKR CSV (pole Listing Exch w Financial Instrument Information)."""
    NASDAQ = "NASDAQ"
    NYSE = "NYSE"
    AEB = "AEB"          # Euronext Amsterdam
    CBOE = "CBOE"        # Opcje US
    ARCA = "ARCA"        # NYSE ARCA
    LSE = "LSE"          # London Stock Exchange
    BILL = "BILL"        # US Treasury Bills (rozliczenie T+1, kalendarz US)


# Data reformy T+1 w USA (SEC Rule 15c6-1)
US_T1_REFORM_DATE = date(2024, 5, 28)

# Planowana reforma T+1 w Europie
EU_T1_REFORM_DATE = date(2027, 10, 11)


@dataclass(frozen=True)
class ExchangeConfig:
    """Konfiguracja giełdy dla obliczania settlement date."""
    listing_exchange: ListingExchange
    calendar_code: str           # kod exchange_calendars (np. "XNAS")

    def settlement_cycle(self, trade_date: date) -> int:
        """Zwraca cykl rozrachunkowy (T+N) dla danej daty transakcji."""
        if self.listing_exchange in {
            ListingExchange.NASDAQ,
            ListingExchange.NYSE,
            ListingExchange.ARCA,
            ListingExchange.CBOE,
            ListingExchange.BILL,
        }:
            return 1 if trade_date >= US_T1_REFORM_DATE else 2
        elif self.listing_exchange == ListingExchange.AEB:
            return 1 if trade_date >= EU_T1_REFORM_DATE else 2
        elif self.listing_exchange == ListingExchange.LSE:
            return 1 if trade_date >= EU_T1_REFORM_DATE else 2
        else:
            raise ValueError(f"Nieznana giełda: {self.listing_exchange}")


# Mapowanie IBKR listing exchange → konfiguracja
EXCHANGE_MAP: dict[str, ExchangeConfig] = {
    "NASDAQ": ExchangeConfig(ListingExchange.NASDAQ, "XNAS"),
    "NYSE": ExchangeConfig(ListingExchange.NYSE, "XNYS"),
    "AEB": ExchangeConfig(ListingExchange.AEB, "XAMS"),
    "CBOE": ExchangeConfig(ListingExchange.CBOE, "XNYS"),  # OCC = US settlement
    "ARCA": ExchangeConfig(ListingExchange.ARCA, "ARCX"),
    "LSE": ExchangeConfig(ListingExchange.LSE, "XLON"),
    "LSEETF": ExchangeConfig(ListingExchange.LSE, "XLON"),  # ETF-y na LSE
    "BILL": ExchangeConfig(ListingExchange.BILL, "XNYS"),  # T-bills: kalendarz US
}


# Mapowanie giełda IBKR → kod kraju ISO 3166-1 alpha-2 (dla PIT/ZG)
EXCHANGE_COUNTRY: dict[str, str] = {
    "NASDAQ": "US",
    "NYSE": "US",
    "ARCA": "US",
    "CBOE": "US",
    "BILL": "US",
    "AEB": "NL",
    "LSE": "GB",
    "LSEETF": "GB",
}


def get_exchange_config(listing_exchange: str) -> ExchangeConfig:
    """Pobierz konfigurację giełdy po kodzie z IBKR CSV."""
    config = EXCHANGE_MAP.get(listing_exchange)
    if config is None:
        raise ValueError(
            f"Nierozpoznana giełda: {listing_exchange}. "
            f"Dostępne: {', '.join(EXCHANGE_MAP.keys())}"
        )
    return config
