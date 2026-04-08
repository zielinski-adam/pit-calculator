"""Model dywidendy i withholding tax z IBKR CSV."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .enums import DividendType, WhtType


class Dividend(BaseModel):
    """Dywidenda z sekcji Dividends CSV."""
    model_config = ConfigDict(frozen=True)

    currency: str                  # np. "USD"
    payment_date: date             # data wpływu na rachunek (kurs NBP D-1 od tej daty)
    symbol: str                    # wyciągnięty z opisu (np. "IBKR")
    isin: str                      # wyciągnięty z opisu (np. "US45841N1072")
    description: str               # pełny opis z CSV
    amount: Decimal                # kwota brutto (dodatnia)
    dividend_type: DividendType    # Cash Dividend lub Payment in Lieu

    @property
    def country(self) -> str:
        """Kraj z prefiksu ISIN -- dla PIT/ZG."""
        return self.isin[:2] if len(self.isin) >= 2 else "XX"


class WithholdingTax(BaseModel):
    """Withholding tax z sekcji Withholding Tax CSV."""
    model_config = ConfigDict(frozen=True)

    currency: str
    payment_date: date
    symbol: str | None = None      # wyciągnięty z opisu (jeśli dividend WHT)
    isin: str | None = None        # wyciągnięty z opisu (jeśli dividend WHT)
    description: str
    amount: Decimal                # kwota WHT (ujemna -- potrącona)
    wht_type: WhtType              # DIVIDEND_WHT lub INTEREST_WHT

    @property
    def country(self) -> str | None:
        """Kraj z prefiksu ISIN (tylko dla dividend WHT)."""
        if self.isin and len(self.isin) >= 2:
            return self.isin[:2]
        return None
