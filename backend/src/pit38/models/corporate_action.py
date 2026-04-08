"""Model corporate action (split) z IBKR CSV."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .enums import CorporateActionType


class CorporateAction(BaseModel):
    """Zdarzenie korporacyjne z sekcji Corporate Actions CSV."""
    model_config = ConfigDict(frozen=True)

    asset_category: str            # np. "Stocks"
    currency: str
    report_date: date
    action_datetime: datetime
    action_date: date              # wyciągnięta z action_datetime
    description: str               # pełny opis z CSV
    symbol: str                    # wyciągnięty z opisu
    isin: str                      # wyciągnięty z opisu
    quantity: Decimal              # zmiana ilości
    action_type: CorporateActionType

    # Pola specyficzne dla splitu
    ratio_from: int | None = None  # np. 1 (w split 4:1)
    ratio_to: int | None = None    # np. 4 (w split 4:1)
