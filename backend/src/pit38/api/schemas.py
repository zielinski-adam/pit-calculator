"""Schematy request/response dla API."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CalculateRequest(BaseModel):
    """Parametry kalkulacji (przesyłane razem z plikiem CSV)."""

    tax_year: int = Field(..., description="Rok podatkowy", ge=2020, le=2030)
    prior_losses: Decimal = Field(
        default=Decimal("0"),
        description="Strata z lat ubiegłych do odliczenia (D.30)",
        ge=0,
    )


class PitZgResponse(BaseModel):
    """PIT/ZG -- wpis per kraj."""
    model_config = ConfigDict(frozen=True)

    country_code: str
    country_name: str
    capital_gains_income: Decimal
    other_income: Decimal
    foreign_tax_paid: Decimal


class TaxLotResponse(BaseModel):
    """Zamknięta pozycja FIFO."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    isin: str
    country: str
    listing_exchange: str
    asset_category: str
    currency: str
    multiplier: int

    buy_trade_date: date
    buy_settle_date: date
    buy_nbp_rate_date: date
    buy_nbp_rate: Decimal
    buy_price: Decimal
    buy_quantity: Decimal
    buy_commission: Decimal
    buy_cost_pln: Decimal

    sell_trade_date: date
    sell_settle_date: date
    sell_nbp_rate_date: date
    sell_nbp_rate: Decimal
    sell_price: Decimal
    sell_quantity: Decimal
    sell_commission: Decimal
    sell_proceeds_pln: Decimal

    profit_loss_pln: Decimal


class TradeResponse(BaseModel):
    """Transakcja z CSV (wzbogacona o settlement date)."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    isin: str
    asset_category: str
    currency: str
    listing_exchange: str
    trade_date: date
    settle_date: date | None
    quantity: Decimal
    price: Decimal
    proceeds: Decimal
    commission: Decimal
    multiplier: int
    codes: list[str]


class DividendResponse(BaseModel):
    """Dywidenda."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    isin: str
    currency: str
    payment_date: date
    amount: Decimal
    dividend_type: str
    description: str


class WhtResponse(BaseModel):
    """Withholding tax."""
    model_config = ConfigDict(frozen=True)

    symbol: str | None
    isin: str | None
    currency: str
    payment_date: date
    amount: Decimal
    wht_type: str
    description: str


class CorporateActionResponse(BaseModel):
    """Corporate action (split)."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    isin: str
    action_date: date
    action_type: str
    description: str
    quantity: Decimal
    ratio_from: int | None
    ratio_to: int | None


class OpenPositionResponse(BaseModel):
    """Otwarta pozycja (lot, który nie został jeszcze zamknięty)."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    remaining_quantity: Decimal
    price_per_unit: Decimal
    trade_date: date
    settle_date: date | None
    currency: str


class CalculateResponse(BaseModel):
    """Pełny wynik kalkulacji PIT-38."""
    model_config = ConfigDict(frozen=True)

    tax_year: int

    # Sekcja C
    c22_proceeds: Decimal
    c23_costs: Decimal
    c26_total_proceeds: Decimal
    c27_total_costs: Decimal
    c28_income: Decimal
    c29_loss: Decimal

    # Sekcja D
    d30_prior_losses: Decimal
    d31_tax_base: Decimal
    d32_tax_rate: Decimal
    d33_tax_calculated: Decimal
    d34_foreign_tax: Decimal
    d35_tax_due: Decimal

    # Sekcja G
    dividends_gross_pln: Decimal
    g47_dividend_tax: Decimal
    g48_dividend_wht: Decimal
    dividend_topup_exact: Decimal
    g49_dividend_difference: Decimal

    # PIT/ZG
    pit_zg_entries: list[PitZgResponse]

    # Suma
    total_tax_due: Decimal

    # Dane szczegółowe
    tax_lots: list[TaxLotResponse]
    trades: list[TradeResponse]
    dividends: list[DividendResponse]
    withholding_taxes: list[WhtResponse]
    corporate_actions: list[CorporateActionResponse]
    open_positions: list[OpenPositionResponse]

    # Metadane
    trades_count: int
    tax_lots_count: int
    dividends_count: int
    warnings: list[str]


class HealthResponse(BaseModel):
    """Odpowiedź health check."""

    status: str = "ok"
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    """Odpowiedź błędu."""

    detail: str
