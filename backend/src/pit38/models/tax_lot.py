"""Model TaxLot -- wynik FIFO engine."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TaxLot(BaseModel):
    """
    Zamknięta pozycja (wynik dopasowania FIFO).

    Każdy TaxLot reprezentuje jedną parę kupno-sprzedaż.
    Kurs NBP jest osobny dla kupna i sprzedaży (każdy z D-1 od SWOJEGO settle_date).
    """
    model_config = ConfigDict(frozen=True)

    # Identyfikacja instrumentu
    symbol: str
    isin: str
    country: str                    # z prefiksu ISIN, dla PIT/ZG
    listing_exchange: str
    asset_category: str             # "Stocks" lub "Equity and Index Options"
    currency: str
    multiplier: int = 1

    # Strona kupna
    buy_trade_date: date
    buy_settle_date: date
    buy_nbp_rate_date: date         # D-1 od buy_settle_date
    buy_nbp_rate: Decimal           # kurs NBP z buy_nbp_rate_date
    buy_price: Decimal              # cena per unit w walucie oryginalnej
    buy_quantity: Decimal           # ilość (dodatnia)
    buy_commission: Decimal         # proporcjonalna prowizja (ujemna)
    buy_cost_pln: Decimal           # (|buy_price × buy_quantity| + |buy_commission|) × buy_nbp_rate

    # Strona sprzedaży
    sell_trade_date: date
    sell_settle_date: date
    sell_nbp_rate_date: date        # D-1 od sell_settle_date
    sell_nbp_rate: Decimal          # kurs NBP z sell_nbp_rate_date
    sell_price: Decimal
    sell_quantity: Decimal           # ilość (dodatnia, = buy_quantity)
    sell_commission: Decimal         # proporcjonalna prowizja (ujemna)
    sell_proceeds_pln: Decimal       # |sell_price × sell_quantity - |sell_commission|| × sell_nbp_rate

    # Wynik
    profit_loss_pln: Decimal         # sell_proceeds_pln - buy_cost_pln

    @property
    def tax_year(self) -> int:
        """Rok podatkowy = rok settlement date sprzedaży."""
        return self.sell_settle_date.year
