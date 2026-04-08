"""Testy silnika FIFO multi-year -- scenariusze z FIFO_MULTI_YEAR.md."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pit38.fifo.engine import FIFOResult, OpenLot, run_fifo
from pit38.models.corporate_action import CorporateAction
from pit38.models.enums import AssetCategory, CorporateActionType
from pit38.models.trade import Trade
from pit38.nbp.client import NBPClient


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────

def _make_trade(
    symbol: str = "AAPL",
    trade_date: date = date(2025, 3, 17),
    settle_date: date = date(2025, 3, 18),
    quantity: int | Decimal = 100,
    price: str = "150.00",
    commission: str = "-1.00",
    currency: str = "USD",
    asset_category: AssetCategory = AssetCategory.STOCKS,
    listing_exchange: str = "NASDAQ",
    isin: str = "US0378331005",
    multiplier: int = 1,
) -> Trade:
    """Stwórz syntetyczny Trade."""
    qty = Decimal(str(quantity))
    dt = datetime(trade_date.year, trade_date.month, trade_date.day, 10, 0, 0)
    proceeds = -(qty * Decimal(price)) if qty > 0 else abs(qty) * Decimal(price)
    return Trade(
        symbol=symbol,
        isin=isin,
        asset_category=asset_category,
        currency=currency,
        listing_exchange=listing_exchange,
        trade_datetime=dt,
        trade_date=trade_date,
        settle_date=settle_date,
        quantity=qty,
        price=Decimal(price),
        proceeds=proceeds,
        commission=Decimal(commission),
        multiplier=multiplier,
    )


def _make_split(
    symbol: str = "AAPL",
    action_date: date = date(2025, 6, 17),
    ratio_from: int = 1,
    ratio_to: int = 4,
    isin: str = "US0378331005",
) -> CorporateAction:
    """Stwórz syntetyczny split."""
    return CorporateAction(
        asset_category="Stocks",
        currency="USD",
        report_date=action_date,
        action_datetime=datetime(action_date.year, action_date.month, action_date.day),
        action_date=action_date,
        description=f"{symbol}({isin}) Split {ratio_to} for {ratio_from}",
        symbol=symbol,
        isin=isin,
        quantity=Decimal("0"),
        action_type=CorporateActionType.SPLIT,
        ratio_from=ratio_from,
        ratio_to=ratio_to,
    )


@pytest.fixture
def mock_nbp() -> MagicMock:
    """Mock NBPClient -- zwraca stały kurs 4.00 PLN/USD."""
    client = MagicMock(spec=NBPClient)
    client.get_rate.return_value = Decimal("4.0000")
    return client


@pytest.fixture
def mock_nbp_varied() -> MagicMock:
    """Mock NBPClient -- zwraca różne kursy per data."""
    rates = {
        # Scenariusz 1: kupno 2023, sprzedaż 2025
        date(2023, 11, 16): Decimal("4.1000"),  # buy NBP
        date(2025, 3, 17): Decimal("3.9000"),    # sell NBP
        # Scenariusz 6: trzy loty multi-year
        date(2022, 3, 16): Decimal("4.3000"),
        date(2023, 6, 21): Decimal("4.1500"),
        date(2024, 9, 10): Decimal("3.9500"),
        date(2025, 4, 15): Decimal("4.0500"),
    }
    client = MagicMock(spec=NBPClient)

    def _get_rate(currency: str, rate_date: date) -> Decimal:
        return rates.get(rate_date, Decimal("4.0000"))

    client.get_rate.side_effect = _get_rate
    return client


# ────────────────────────────────────────────────────────────
# Podstawowe operacje FIFO
# ────────────────────────────────────────────────────────────

class TestBasicFIFO:
    """Podstawowe operacje kupno-sprzedaż."""

    @pytest.mark.fifo
    def test_simple_buy_sell(self, mock_nbp: MagicMock):
        """Kupno 100 + sprzedaż 100 → 1 TaxLot."""
        trades = [
            _make_trade(quantity=100, price="150.00",
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            _make_trade(quantity=-100, price="160.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        assert len(result.tax_lots) == 1
        lot = result.tax_lots[0]
        assert lot.buy_quantity == Decimal("100")
        assert lot.sell_quantity == Decimal("100")
        assert lot.buy_price == Decimal("150.00")
        assert lot.sell_price == Decimal("160.00")
        assert lot.profit_loss_pln > 0  # zysk

    @pytest.mark.fifo
    def test_no_sells_no_tax_lots(self, mock_nbp: MagicMock):
        """Same kupna → 0 TaxLots, otwarte pozycje."""
        trades = [
            _make_trade(quantity=100, trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        assert len(result.tax_lots) == 0
        assert "AAPL" in result.open_positions
        assert len(result.open_positions["AAPL"]) == 1

    @pytest.mark.fifo
    def test_partial_sell(self, mock_nbp: MagicMock):
        """Kupno 100 + sprzedaż 60 → 1 TaxLot, 40 otwarte."""
        trades = [
            _make_trade(quantity=100, price="150.00",
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            _make_trade(quantity=-60, price="160.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        assert len(result.tax_lots) == 1
        assert result.tax_lots[0].buy_quantity == Decimal("60")
        assert result.tax_lots[0].sell_quantity == Decimal("60")

        # Zostaje 40
        assert "AAPL" in result.open_positions
        remaining = result.open_positions["AAPL"][0].remaining_quantity
        assert remaining == Decimal("40")

    @pytest.mark.fifo
    def test_fifo_order(self, mock_nbp: MagicMock):
        """FIFO: pierwszy lot kupna jest zużywany pierwszy."""
        trades = [
            _make_trade(quantity=100, price="100.00",
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            _make_trade(quantity=100, price="200.00",
                        trade_date=date(2025, 2, 10), settle_date=date(2025, 2, 11)),
            _make_trade(quantity=-100, price="150.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        assert len(result.tax_lots) == 1
        # FIFO: pierwszy lot (100 @ 100) powinien być dopasowany
        assert result.tax_lots[0].buy_price == Decimal("100.00")

    @pytest.mark.fifo
    def test_sell_across_two_lots(self, mock_nbp: MagicMock):
        """Sprzedaż przekraczająca jeden lot → 2 TaxLoty."""
        trades = [
            _make_trade(quantity=50, price="100.00",
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            _make_trade(quantity=50, price="200.00",
                        trade_date=date(2025, 2, 10), settle_date=date(2025, 2, 11)),
            _make_trade(quantity=-80, price="150.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        assert len(result.tax_lots) == 2
        # Lot 1: 50 z pierwszego kupna
        assert result.tax_lots[0].buy_quantity == Decimal("50")
        assert result.tax_lots[0].buy_price == Decimal("100.00")
        # Lot 2: 30 z drugiego kupna
        assert result.tax_lots[1].buy_quantity == Decimal("30")
        assert result.tax_lots[1].buy_price == Decimal("200.00")

        # Zostaje 20
        assert result.open_positions["AAPL"][0].remaining_quantity == Decimal("20")


# ────────────────────────────────────────────────────────────
# Sortowanie po settle_date (KRYTYCZNE!)
# ────────────────────────────────────────────────────────────

class TestSettleDateOrdering:
    """FIFO sortuje po (settle_date, trade_date), nie po trade_date."""

    @pytest.mark.fifo
    @pytest.mark.settlement
    def test_settle_date_ordering(self, mock_nbp: MagicMock):
        """
        Scenariusz 5: Trade z 2024-05-27 (T+2) i 2024-05-28 (T+1)
        oba settle na 2024-05-29. Sort stabilny po trade_date.
        """
        trades = [
            # T+2 (przed reformą) -- settle 2024-05-29
            _make_trade(quantity=100, price="100.00",
                        trade_date=date(2024, 5, 27), settle_date=date(2024, 5, 29)),
            # T+1 (po reformie) -- też settle 2024-05-29
            _make_trade(quantity=100, price="200.00",
                        trade_date=date(2024, 5, 28), settle_date=date(2024, 5, 29)),
            # Sprzedaż
            _make_trade(quantity=-100, price="150.00",
                        trade_date=date(2024, 6, 10), settle_date=date(2024, 6, 11)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        assert len(result.tax_lots) == 1
        # FIFO: trade z 05-27 powinien być pierwszy (ten sam settle_date, wcześniejszy trade_date)
        assert result.tax_lots[0].buy_trade_date == date(2024, 5, 27)


# ────────────────────────────────────────────────────────────
# Multi-year FIFO
# ────────────────────────────────────────────────────────────

class TestMultiYear:
    """Scenariusze multi-year z FIFO_MULTI_YEAR.md."""

    @pytest.mark.fifo
    def test_scenario1_multi_year_pre_post_reform(self, mock_nbp_varied: MagicMock):
        """
        Scenariusz 1: Kupno 2023 (T+2), sprzedaż 2025 (T+1).
        Każdy lot ma WŁASNY kurs NBP.
        """
        trades = [
            _make_trade(quantity=100, price="150.00",
                        trade_date=date(2023, 11, 15), settle_date=date(2023, 11, 17)),
            _make_trade(quantity=-100, price="180.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        ]
        result = run_fifo(trades, [], mock_nbp_varied)

        assert len(result.tax_lots) == 1
        lot = result.tax_lots[0]
        assert lot.buy_trade_date == date(2023, 11, 15)
        assert lot.sell_trade_date == date(2025, 3, 17)
        assert lot.tax_year == 2025

        # Kurs NBP kupna: D-1 od 2023-11-17 = 2023-11-16 → 4.1000
        assert lot.buy_nbp_rate == Decimal("4.1000")
        # Kurs NBP sprzedaży: D-1 od 2025-03-18 = 2025-03-17 → 3.9000
        assert lot.sell_nbp_rate == Decimal("3.9000")

    @pytest.mark.fifo
    def test_scenario6_three_lots_multi_year(self, mock_nbp_varied: MagicMock):
        """
        Scenariusz 6: Trzy kupna (2022, 2023, 2024), sprzedaż 250 w 2025.
        FIFO: 100 z 2022, 100 z 2023, 50 z 2024.
        """
        trades = [
            _make_trade(quantity=100, price="150.00",
                        trade_date=date(2022, 3, 15), settle_date=date(2022, 3, 17)),
            _make_trade(quantity=100, price="170.00",
                        trade_date=date(2023, 6, 20), settle_date=date(2023, 6, 22)),
            _make_trade(quantity=100, price="180.00",
                        trade_date=date(2024, 9, 10), settle_date=date(2024, 9, 11)),
            _make_trade(quantity=-250, price="200.00",
                        trade_date=date(2025, 4, 15), settle_date=date(2025, 4, 16)),
        ]
        result = run_fifo(trades, [], mock_nbp_varied)

        assert len(result.tax_lots) == 3
        # Lot 1: 100 z 2022
        assert result.tax_lots[0].buy_quantity == Decimal("100")
        assert result.tax_lots[0].buy_trade_date == date(2022, 3, 15)
        assert result.tax_lots[0].buy_nbp_rate == Decimal("4.3000")
        # Lot 2: 100 z 2023
        assert result.tax_lots[1].buy_quantity == Decimal("100")
        assert result.tax_lots[1].buy_trade_date == date(2023, 6, 20)
        assert result.tax_lots[1].buy_nbp_rate == Decimal("4.1500")
        # Lot 3: 50 z 2024 (częściowy)
        assert result.tax_lots[2].buy_quantity == Decimal("50")
        assert result.tax_lots[2].buy_trade_date == date(2024, 9, 10)
        assert result.tax_lots[2].buy_nbp_rate == Decimal("3.9500")

        # Zostaje 50 z 2024
        assert result.open_positions["AAPL"][0].remaining_quantity == Decimal("50")

        # Wszystkie mają ten sam kurs sell NBP
        for lot in result.tax_lots:
            assert lot.sell_nbp_rate == Decimal("4.0500")
            assert lot.tax_year == 2025

    @pytest.mark.fifo
    def test_tax_year_filter(self, mock_nbp: MagicMock):
        """Filtrowanie po roku podatkowym."""
        trades = [
            _make_trade(quantity=100, price="150.00",
                        trade_date=date(2024, 6, 10), settle_date=date(2024, 6, 11)),
            # Sprzedaż w 2024
            _make_trade(quantity=-50, price="160.00",
                        trade_date=date(2024, 9, 10), settle_date=date(2024, 9, 11)),
            # Sprzedaż w 2025
            _make_trade(quantity=-50, price="170.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        ]
        result_2025 = run_fifo(trades, [], mock_nbp, tax_year=2025)
        result_2024 = run_fifo(trades, [], mock_nbp, tax_year=2024)
        result_all = run_fifo(trades, [], mock_nbp)

        assert len(result_2025.tax_lots) == 1
        assert result_2025.tax_lots[0].tax_year == 2025
        assert len(result_2024.tax_lots) == 1
        assert result_2024.tax_lots[0].tax_year == 2024
        assert len(result_all.tax_lots) == 2


# ────────────────────────────────────────────────────────────
# Brzeg roku (KRYTYCZNE!)
# ────────────────────────────────────────────────────────────

class TestYearBoundary:
    """Trade z końca grudnia z settle w następnym roku."""

    @pytest.mark.fifo
    @pytest.mark.boundary
    def test_dec31_trade_year_2026(self, mock_nbp: MagicMock):
        """
        Scenariusz 2: Trade NYSE 2025-12-31, settle 2026-01-02.
        TaxLot.tax_year = 2026, NIE 2025.
        """
        trades = [
            _make_trade(quantity=100, price="150.00",
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            _make_trade(quantity=-100, price="160.00",
                        trade_date=date(2025, 12, 31), settle_date=date(2026, 1, 2)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        assert len(result.tax_lots) == 1
        assert result.tax_lots[0].tax_year == 2026

    @pytest.mark.fifo
    @pytest.mark.boundary
    def test_dec30_trade_year_2025(self, mock_nbp: MagicMock):
        """
        Scenariusz 2: Trade NYSE 2025-12-30, settle 2025-12-31.
        TaxLot.tax_year = 2025.
        """
        trades = [
            _make_trade(quantity=100, price="150.00",
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            _make_trade(quantity=-100, price="160.00",
                        trade_date=date(2025, 12, 30), settle_date=date(2025, 12, 31)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        assert len(result.tax_lots) == 1
        assert result.tax_lots[0].tax_year == 2025


# ────────────────────────────────────────────────────────────
# Split handling
# ────────────────────────────────────────────────────────────

class TestSplit:
    """Corporate actions -- splity."""

    @pytest.mark.fifo
    def test_split_adjusts_quantity_and_price(self, mock_nbp: MagicMock):
        """
        Scenariusz 4: Kupno 100 @ 400 → split 4:1 → 400 @ 100.
        Łączny koszt niezmieniony.
        """
        trades = [
            _make_trade(quantity=100, price="400.00",
                        trade_date=date(2022, 5, 10), settle_date=date(2022, 5, 12)),
        ]
        splits = [
            _make_split(symbol="AAPL", action_date=date(2022, 8, 28),
                        ratio_from=1, ratio_to=4),
        ]
        # Dodaj sprzedaż po splicie
        trades.append(
            _make_trade(quantity=-200, price="110.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        )

        result = run_fifo(trades, splits, mock_nbp)

        assert len(result.tax_lots) == 1
        lot = result.tax_lots[0]
        # Po splicie: cena = 400/4 = 100
        assert lot.buy_price == Decimal("100.00")
        # Ilość dopasowana = 200
        assert lot.buy_quantity == Decimal("200")

        # Zostaje 200 (400 - 200)
        assert result.open_positions["AAPL"][0].remaining_quantity == Decimal("200")

    @pytest.mark.fifo
    def test_split_total_cost_unchanged(self, mock_nbp: MagicMock):
        """Split nie zmienia łącznego kosztu lotu."""
        trades = [
            _make_trade(quantity=100, price="400.00", commission="-10.00",
                        trade_date=date(2022, 5, 10), settle_date=date(2022, 5, 12)),
        ]
        splits = [
            _make_split(symbol="AAPL", action_date=date(2022, 8, 28),
                        ratio_from=1, ratio_to=4),
        ]
        # Sprzedaj wszystko po splicie
        trades.append(
            _make_trade(quantity=-400, price="110.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        )

        result = run_fifo(trades, splits, mock_nbp)

        lot = result.tax_lots[0]
        # Koszt kupna: (100 × 400 + 10) × 4.0 = 160040 PLN
        # Ale po splicie: (400 × 100 + 10) × 4.0 = 160040 PLN -- to samo!
        expected_cost = (Decimal("400") * Decimal("100") + Decimal("10")) * Decimal("4.0000")
        assert lot.buy_cost_pln == expected_cost


# ────────────────────────────────────────────────────────────
# Prowizje
# ────────────────────────────────────────────────────────────

class TestCommissions:
    """Proporcjonalne prowizje."""

    @pytest.mark.fifo
    def test_proportional_buy_commission(self, mock_nbp: MagicMock):
        """Prowizja kupna dzielona proporcjonalnie przy częściowej sprzedaży."""
        trades = [
            _make_trade(quantity=100, price="150.00", commission="-10.00",
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            _make_trade(quantity=-60, price="160.00", commission="-6.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        lot = result.tax_lots[0]
        # Prowizja kupna proporcjonalna: -10 × (60/100) = -6
        assert lot.buy_commission == Decimal("-6.00")
        # Prowizja sprzedaży: pełna bo cała sprzedaż = 1 lot
        assert lot.sell_commission == Decimal("-6.00")

    @pytest.mark.fifo
    def test_commission_affects_cost_and_proceeds(self, mock_nbp: MagicMock):
        """Prowizja kupna zwiększa koszt, prowizja sprzedaży zmniejsza przychód."""
        trades = [
            _make_trade(quantity=100, price="100.00", commission="-10.00",
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            _make_trade(quantity=-100, price="100.00", commission="-10.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        lot = result.tax_lots[0]
        rate = Decimal("4.0000")
        # Koszt: (100 × 100 + 10) × 4 = 40040
        assert lot.buy_cost_pln == (Decimal("10000") + Decimal("10")) * rate
        # Przychód: (100 × 100 - 10) × 4 = 39960
        assert lot.sell_proceeds_pln == (Decimal("10000") - Decimal("10")) * rate
        # Zysk ujemny (prowizje zjadły zysk)
        assert lot.profit_loss_pln < 0


# ────────────────────────────────────────────────────────────
# Osobne koszyki per instrument
# ────────────────────────────────────────────────────────────

class TestBaskets:
    """Osobne koszyki FIFO per instrument."""

    @pytest.mark.fifo
    def test_separate_symbols(self, mock_nbp: MagicMock):
        """AAPL i MSFT mają osobne koszyki."""
        trades = [
            _make_trade(symbol="AAPL", quantity=100, price="150.00",
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            _make_trade(symbol="MSFT", quantity=50, price="400.00", isin="US5949181045",
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            _make_trade(symbol="AAPL", quantity=-100, price="160.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        assert len(result.tax_lots) == 1
        assert result.tax_lots[0].symbol == "AAPL"
        # MSFT nadal otwarty
        assert "MSFT" in result.open_positions

    @pytest.mark.fifo
    def test_option_separate_from_stock(self, mock_nbp: MagicMock):
        """Opcja NBIS 20MAR26 150 C to osobny koszyk od akcji NBIS."""
        trades = [
            _make_trade(symbol="NBIS", quantity=100, price="50.00",
                        isin="NL0009805522",
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            _make_trade(symbol="NBIS 20MAR26 150 C", quantity=5, price="12.90",
                        asset_category=AssetCategory.OPTIONS,
                        listing_exchange="CBOE", isin="NL0009805522",
                        multiplier=100,
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            # Sprzedaż opcji
            _make_trade(symbol="NBIS 20MAR26 150 C", quantity=-5, price="15.00",
                        asset_category=AssetCategory.OPTIONS,
                        listing_exchange="CBOE", isin="NL0009805522",
                        multiplier=100,
                        trade_date=date(2025, 2, 10), settle_date=date(2025, 2, 11)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        assert len(result.tax_lots) == 1
        assert result.tax_lots[0].symbol == "NBIS 20MAR26 150 C"
        # Akcja NBIS nadal otwarta
        assert "NBIS" in result.open_positions
        assert "NBIS 20MAR26 150 C" not in result.open_positions


# ────────────────────────────────────────────────────────────
# Decimal -- nigdy float
# ────────────────────────────────────────────────────────────

class TestDecimalSafety:
    """Wszystkie kwoty muszą być Decimal."""

    @pytest.mark.fifo
    def test_all_amounts_decimal(self, mock_nbp: MagicMock):
        """Każda kwota w TaxLot to Decimal."""
        trades = [
            _make_trade(quantity=100, price="150.00",
                        trade_date=date(2025, 1, 6), settle_date=date(2025, 1, 7)),
            _make_trade(quantity=-100, price="160.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        lot = result.tax_lots[0]
        decimal_fields = [
            lot.buy_nbp_rate, lot.buy_price, lot.buy_quantity,
            lot.buy_commission, lot.buy_cost_pln,
            lot.sell_nbp_rate, lot.sell_price, lot.sell_quantity,
            lot.sell_commission, lot.sell_proceeds_pln,
            lot.profit_loss_pln,
        ]
        for val in decimal_fields:
            assert isinstance(val, Decimal), f"Oczekiwano Decimal, dostano {type(val)}: {val}"


# ────────────────────────────────────────────────────────────
# Walidacja
# ────────────────────────────────────────────────────────────

class TestValidation:
    """Walidacja danych wejściowych."""

    @pytest.mark.fifo
    def test_missing_settle_date_raises(self, mock_nbp: MagicMock):
        """Trade bez settle_date → ValueError."""
        trades = [
            _make_trade(quantity=100, settle_date=None,
                        trade_date=date(2025, 1, 6)),
        ]
        with pytest.raises(ValueError, match="settle_date"):
            run_fifo(trades, [], mock_nbp)

    @pytest.mark.fifo
    def test_short_sell_warning(self, mock_nbp: MagicMock):
        """Sprzedaż bez otwartej pozycji → warning."""
        trades = [
            _make_trade(quantity=-100, price="150.00",
                        trade_date=date(2025, 3, 17), settle_date=date(2025, 3, 18)),
        ]
        result = run_fifo(trades, [], mock_nbp)

        assert len(result.warnings) >= 1
        assert "Short sell" in result.warnings[0] or "brak otwartych" in result.warnings[0]


# ────────────────────────────────────────────────────────────
# Integracja z prawdziwymi danymi
# ────────────────────────────────────────────────────────────

class TestIntegration:
    """Integracja FIFO z parserem i settlement calculator."""

    @pytest.mark.fifo
    def test_real_data_no_errors(self):
        """Pełny pipeline na prawdziwych danych -- bez wyjątków."""
        fixture = Path(__file__).parent.parent.parent / "resources" / "U15663971_20241230_20251230.csv"
        if not fixture.exists():
            pytest.skip("Brak fixture CSV")

        from pit38.parsers.ibkr_csv import parse_ibkr_csv
        from pit38.settlement.calculator import enrich_trades_with_settlement

        parsed = parse_ibkr_csv(fixture)
        enriched = enrich_trades_with_settlement(parsed.trades)

        # Mock NBP żeby nie odpytywać API
        mock_nbp = MagicMock(spec=NBPClient)
        mock_nbp.get_rate.return_value = Decimal("4.0000")

        result = run_fifo(enriched, parsed.corporate_actions, mock_nbp)

        # Powinny być jakieś zamknięte pozycje (sprzedaże w danych)
        assert len(result.tax_lots) > 0
        # Każdy TaxLot ma poprawne dane
        for lot in result.tax_lots:
            assert lot.buy_quantity > 0
            assert lot.sell_quantity > 0
            assert lot.buy_settle_date >= lot.buy_trade_date
            assert lot.sell_settle_date >= lot.sell_trade_date
            assert isinstance(lot.profit_loss_pln, Decimal)
