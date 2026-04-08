"""Model transakcji (Trade) z IBKR CSV."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from .enums import AssetCategory, BuySell


class Trade(BaseModel):
    """
    Transakcja kupna/sprzedaży z IBKR Activity Statement CSV.

    Settlement date NIE pochodzi z CSV -- jest obliczany z exchange_calendars
    na podstawie trade_date + listing_exchange.
    """
    model_config = ConfigDict(frozen=True)

    # Identyfikacja
    symbol: str                    # np. "AAPL", "NBIS 20MAR26 150 C"
    isin: str                      # z Financial Instrument Information (np. "US0378331005")
    asset_category: AssetCategory  # Stocks lub Options
    currency: str                  # np. "USD", "EUR"
    listing_exchange: str          # np. "NASDAQ", "NYSE", "AEB", "CBOE"

    # Daty
    trade_datetime: datetime       # data i czas zawarcia transakcji
    trade_date: date               # tylko data (bez czasu), wyciągnięta z trade_datetime
    settle_date: date | None = None  # obliczany po parsowaniu z exchange_calendars

    # Kwoty -- ZAWSZE Decimal, NIGDY float
    quantity: Decimal              # dodatnia = kupno, ujemna = sprzedaż
    price: Decimal                 # cena per unit w walucie oryginalnej
    proceeds: Decimal              # kwota transakcji (ujemna = kupno, dodatnia = sprzedaż)
    commission: Decimal            # prowizja (zazwyczaj ujemna, ale może być dodatnia = rebate)

    # Opcje
    multiplier: int = 1            # 1 dla akcji, 100 dla opcji
    underlying: str | None = None  # symbol underlying (np. "NBIS" dla opcji NBIS 20MAR26 150 C)
    expiry: date | None = None     # data wygaśnięcia opcji
    strike: Decimal | None = None  # cena strike opcji
    option_type: str | None = None # "C" (call) lub "P" (put)

    # Metadane
    codes: list[str] = []          # kody IBKR: O, C, P, Ep, Ex, A itp.

    @field_validator("quantity", "price", "proceeds", "commission", mode="before")
    @classmethod
    def _parse_decimal(cls, v: str | int | float | Decimal) -> Decimal:
        """Parsuj wartości na Decimal -- obsługuje stringi z przecinkami (np. '1,000')."""
        if isinstance(v, str):
            return Decimal(v.replace(",", ""))
        return Decimal(str(v))

    @property
    def buy_sell(self) -> BuySell:
        """Kierunek transakcji wyznaczany z quantity."""
        return BuySell.BUY if self.quantity > 0 else BuySell.SELL

    @property
    def is_buy(self) -> bool:
        return self.quantity > 0

    @property
    def is_sell(self) -> bool:
        return self.quantity < 0

    @property
    def is_option(self) -> bool:
        return self.asset_category == AssetCategory.OPTIONS

    @property
    def is_expiration(self) -> bool:
        """Czy trade to wygaśnięcie opcji (kod Ep)."""
        return "Ep" in self.codes

    @property
    def is_exercise(self) -> bool:
        """Czy trade to wykonanie opcji (kod Ex)."""
        return "Ex" in self.codes

    @property
    def is_assignment(self) -> bool:
        """Czy trade to przydzielenie opcji (kod A)."""
        return "A" in self.codes

    @property
    def country(self) -> str:
        """Kraj giełdy (z listing_exchange) -- dla PIT/ZG."""
        from .exchange import EXCHANGE_COUNTRY
        return EXCHANGE_COUNTRY.get(self.listing_exchange, self.isin[:2])

    @property
    def tax_year(self) -> int | None:
        """Rok podatkowy = rok settle_date. None jeśli settle_date nie obliczony."""
        return self.settle_date.year if self.settle_date else None


class InstrumentInfo(BaseModel):
    """
    Informacje o instrumencie z sekcji Financial Instrument Information CSV.
    Służy jako lookup table: symbol → (ISIN, giełda, multiplier).
    """
    model_config = ConfigDict(frozen=True)

    asset_category: AssetCategory
    symbol: str                     # klucz lookup (np. "AAPL", "NBIS  260320C00150000")
    description: str
    conid: int
    isin: str                       # Security ID = ISIN
    listing_exchange: str           # Listing Exch
    multiplier: int = 1
    underlying: str | None = None   # tylko dla opcji
    instrument_type: str = ""       # COMMON, ETF, itp.

    # Pola opcyjne (tylko dla opcji)
    expiry: date | None = None
    strike: Decimal | None = None
    option_type: str | None = None  # "C" (call) lub "P" (put)

    @property
    def country(self) -> str:
        """Kraj giełdy (z listing_exchange) -- dla PIT/ZG."""
        from .exchange import EXCHANGE_COUNTRY
        return EXCHANGE_COUNTRY.get(self.listing_exchange, self.isin[:2])
