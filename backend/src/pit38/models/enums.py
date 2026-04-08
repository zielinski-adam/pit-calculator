"""Enumy domenowe kalkulatora PIT-38."""
from enum import StrEnum


class AssetCategory(StrEnum):
    """Kategoria instrumentu z IBKR CSV."""
    STOCKS = "Stocks"
    OPTIONS = "Equity and Index Options"
    TREASURY_BILLS = "Treasury Bills"


class BuySell(StrEnum):
    """Kierunek transakcji -- wyznaczany z quantity (>0 = BUY, <0 = SELL)."""
    BUY = "BUY"
    SELL = "SELL"


class TradeCode(StrEnum):
    """Kody transakcji z IBKR CSV (pole Code). Mogą wystąpić jako kombinacja np. 'C;P'."""
    OPEN = "O"
    CLOSE = "C"
    PARTIAL = "P"
    EXPIRED = "Ep"       # Wygaśnięcie pozycji opcyjnej
    EXERCISE = "Ex"      # Wykonanie opcji (kupujący)
    ASSIGNMENT = "A"     # Przydzielenie opcji (sprzedający)


class CorporateActionType(StrEnum):
    """Typ zdarzenia korporacyjnego."""
    SPLIT = "SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"


class DividendType(StrEnum):
    """Typ dywidendy."""
    CASH_DIVIDEND = "CASH_DIVIDEND"
    PAYMENT_IN_LIEU = "PAYMENT_IN_LIEU"


class WhtType(StrEnum):
    """Typ withholding tax."""
    DIVIDEND_WHT = "DIVIDEND_WHT"        # WHT na dywidendy -- sekcja G PIT-38
    INTEREST_WHT = "INTEREST_WHT"        # WHT na odsetki -- PIT-36 (out of scope)
