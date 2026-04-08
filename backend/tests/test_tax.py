"""Testy kalkulatora PIT-38 -- sekcje C, D, G, PIT/ZG."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pit38.models.dividend import Dividend, WithholdingTax
from pit38.models.enums import AssetCategory, DividendType, WhtType
from pit38.models.tax_lot import TaxLot
from pit38.nbp.client import NBPClient
from pit38.tax.calculator import calculate_pit38


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────

def _make_tax_lot(
    symbol: str = "AAPL",
    isin: str = "US0378331005",
    country: str = "US",
    buy_cost_pln: str = "40000.00",
    sell_proceeds_pln: str = "50000.00",
    sell_settle_date: date = date(2025, 3, 18),
    listing_exchange: str = "NASDAQ",
    currency: str = "USD",
) -> TaxLot:
    """Uproszczony TaxLot do testów kalkulatora."""
    buy_cost = Decimal(buy_cost_pln)
    sell_proceeds = Decimal(sell_proceeds_pln)
    return TaxLot(
        symbol=symbol,
        isin=isin,
        country=country,
        listing_exchange=listing_exchange,
        asset_category=AssetCategory.STOCKS,
        currency=currency,
        buy_trade_date=date(2025, 1, 6),
        buy_settle_date=date(2025, 1, 7),
        buy_nbp_rate_date=date(2025, 1, 6),
        buy_nbp_rate=Decimal("4.0000"),
        buy_price=Decimal("150.00"),
        buy_quantity=Decimal("100"),
        buy_commission=Decimal("-1.00"),
        buy_cost_pln=buy_cost,
        sell_trade_date=date(2025, 3, 17),
        sell_settle_date=sell_settle_date,
        sell_nbp_rate_date=date(2025, 3, 17),
        sell_nbp_rate=Decimal("4.0000"),
        sell_price=Decimal("160.00"),
        sell_quantity=Decimal("100"),
        sell_commission=Decimal("-1.00"),
        sell_proceeds_pln=sell_proceeds,
        profit_loss_pln=sell_proceeds - buy_cost,
    )


def _make_dividend(
    amount: str = "100.00",
    payment_date: date = date(2025, 6, 15),
    currency: str = "USD",
    isin: str = "US45841N1072",
    symbol: str = "IBKR",
) -> Dividend:
    return Dividend(
        currency=currency,
        payment_date=payment_date,
        symbol=symbol,
        isin=isin,
        description=f"{symbol}({isin}) Cash Dividend",
        amount=Decimal(amount),
        dividend_type=DividendType.CASH_DIVIDEND,
    )


def _make_wht(
    amount: str = "-15.00",
    payment_date: date = date(2025, 6, 15),
    currency: str = "USD",
    isin: str = "US45841N1072",
    symbol: str = "IBKR",
) -> WithholdingTax:
    return WithholdingTax(
        currency=currency,
        payment_date=payment_date,
        symbol=symbol,
        isin=isin,
        description=f"{symbol}({isin}) Cash Dividend - US Tax",
        amount=Decimal(amount),
        wht_type=WhtType.DIVIDEND_WHT,
    )


@pytest.fixture
def mock_nbp() -> MagicMock:
    """Mock NBPClient -- stały kurs 4.00."""
    client = MagicMock(spec=NBPClient)
    client.get_rate.return_value = Decimal("4.0000")
    return client


# ────────────────────────────────────────────────────────────
# Sekcja C -- zyski kapitałowe
# ────────────────────────────────────────────────────────────

class TestSectionC:
    """Sekcja C -- przychody i koszty."""

    def test_basic_profit(self, mock_nbp: MagicMock):
        """Zysk: przychód > koszt."""
        lots = [_make_tax_lot(buy_cost_pln="40000", sell_proceeds_pln="50000")]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        assert report.c22_proceeds == Decimal("50000.00")
        assert report.c23_costs == Decimal("40000.00")
        assert report.c28_income == Decimal("10000.00")
        assert report.c29_loss == Decimal("0")

    def test_basic_loss(self, mock_nbp: MagicMock):
        """Strata: koszt > przychód."""
        lots = [_make_tax_lot(buy_cost_pln="50000", sell_proceeds_pln="40000")]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        assert report.c28_income == Decimal("0")
        assert report.c29_loss == Decimal("10000.00")

    def test_multiple_lots_sum(self, mock_nbp: MagicMock):
        """Wiele lotów -- sumy."""
        lots = [
            _make_tax_lot(buy_cost_pln="10000", sell_proceeds_pln="15000"),
            _make_tax_lot(buy_cost_pln="20000", sell_proceeds_pln="18000", symbol="MSFT"),
        ]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        assert report.c22_proceeds == Decimal("33000.00")
        assert report.c23_costs == Decimal("30000.00")
        assert report.c28_income == Decimal("3000.00")

    def test_c26_equals_c22(self, mock_nbp: MagicMock):
        """C.26 = C.22 (bo C.20 = 0)."""
        lots = [_make_tax_lot()]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        assert report.c26_total_proceeds == report.c22_proceeds
        assert report.c27_total_costs == report.c23_costs

    def test_no_lots_zero(self, mock_nbp: MagicMock):
        """Brak lotów → wszystko zero."""
        report = calculate_pit38([], [], [], mock_nbp, 2025)

        assert report.c22_proceeds == Decimal("0.00")
        assert report.c23_costs == Decimal("0.00")
        assert report.c28_income == Decimal("0")
        assert report.c29_loss == Decimal("0")


# ────────────────────────────────────────────────────────────
# Sekcja D -- obliczenie podatku
# ────────────────────────────────────────────────────────────

class TestSectionD:
    """Sekcja D -- podatek 19%."""

    def test_tax_19_percent(self, mock_nbp: MagicMock):
        """Podatek = 19% od podstawy."""
        lots = [_make_tax_lot(buy_cost_pln="40000", sell_proceeds_pln="50000")]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        # Dochód = 10000, podstawa = 10000 (zaokr. w dół)
        assert report.d31_tax_base == Decimal("10000")
        # 19% × 10000 = 1900
        assert report.d33_tax_calculated == Decimal("1900.00")
        assert report.d35_tax_due == Decimal("1900")

    def test_tax_base_rounded_down(self, mock_nbp: MagicMock):
        """Podstawa zaokrąglona w dół do pełnych PLN."""
        lots = [_make_tax_lot(buy_cost_pln="39999.50", sell_proceeds_pln="50000.00")]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        # Dochód = 10000.50 → podstawa = 10000 (floor)
        assert report.d31_tax_base == Decimal("10000")

    def test_prior_losses_deduction(self, mock_nbp: MagicMock):
        """Strata z lat ubiegłych zmniejsza podstawę."""
        lots = [_make_tax_lot(buy_cost_pln="40000", sell_proceeds_pln="50000")]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025, prior_losses=Decimal("3000"))

        assert report.d30_prior_losses == Decimal("3000")
        # Podstawa = 10000 - 3000 = 7000
        assert report.d31_tax_base == Decimal("7000")
        # Podatek = 19% × 7000 = 1330
        assert report.d35_tax_due == Decimal("1330")

    def test_prior_losses_exceed_income(self, mock_nbp: MagicMock):
        """Strata > dochód → podstawa = 0, podatek = 0."""
        lots = [_make_tax_lot(buy_cost_pln="40000", sell_proceeds_pln="50000")]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025, prior_losses=Decimal("15000"))

        assert report.d31_tax_base == Decimal("0")
        assert report.d35_tax_due == Decimal("0")

    def test_loss_year_no_tax(self, mock_nbp: MagicMock):
        """Rok ze stratą → podatek = 0."""
        lots = [_make_tax_lot(buy_cost_pln="50000", sell_proceeds_pln="40000")]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        assert report.d31_tax_base == Decimal("0")
        assert report.d35_tax_due == Decimal("0")

    def test_d34_always_zero(self, mock_nbp: MagicMock):
        """D.34 = 0 (IBKR nie pobiera podatku od zysków kapitałowych)."""
        lots = [_make_tax_lot()]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        assert report.d34_foreign_tax == Decimal("0")


# ────────────────────────────────────────────────────────────
# Sekcja G -- dywidendy
# ────────────────────────────────────────────────────────────

class TestSectionG:
    """Sekcja G -- dywidendy zagraniczne."""

    def test_dividend_tax(self, mock_nbp: MagicMock):
        """G.47 = 19% × suma dywidend brutto w PLN."""
        divs = [_make_dividend(amount="100.00")]
        report = calculate_pit38([], divs, [], mock_nbp, 2025)

        # 100 USD × 4.0 = 400 PLN brutto
        assert report.dividends_gross_pln == Decimal("400.00")
        # 19% × 400 = 76
        assert report.g47_dividend_tax == Decimal("76.00")

    def test_wht_deduction(self, mock_nbp: MagicMock):
        """G.48 = WHT w PLN, G.49 = G.47 - G.48."""
        divs = [_make_dividend(amount="100.00")]
        whts = [_make_wht(amount="-15.00")]  # 15% WHT
        report = calculate_pit38([], divs, whts, mock_nbp, 2025)

        # WHT: |-15| × 4.0 = 60 PLN
        assert report.g48_dividend_wht == Decimal("60.00")
        # Dopłata: 76 - 60 = 16
        assert report.g49_dividend_difference == Decimal("16")

    def test_wht_capped_at_g47(self, mock_nbp: MagicMock):
        """WHT nie może przekroczyć G.47."""
        divs = [_make_dividend(amount="100.00")]
        # WHT > 19% dywidendy (np. 35% Szwajcaria bez umowy)
        whts = [_make_wht(amount="-35.00")]
        report = calculate_pit38([], divs, whts, mock_nbp, 2025)

        # G.47 = 76.00
        # WHT = 35 × 4 = 140, ale cap = 76
        assert report.g48_dividend_wht == Decimal("76.00")
        assert report.g49_dividend_difference == Decimal("0")

    def test_no_dividends(self, mock_nbp: MagicMock):
        """Brak dywidend → sekcja G zerowa."""
        report = calculate_pit38([], [], [], mock_nbp, 2025)

        assert report.dividends_gross_pln == Decimal("0.00")
        assert report.g47_dividend_tax == Decimal("0.00")
        assert report.g48_dividend_wht == Decimal("0.00")
        assert report.g49_dividend_difference == Decimal("0")

    def test_dividend_year_filter(self, mock_nbp: MagicMock):
        """Tylko dywidendy z danego roku podatkowego."""
        divs = [
            _make_dividend(amount="100.00", payment_date=date(2025, 6, 15)),
            _make_dividend(amount="200.00", payment_date=date(2024, 6, 15)),
        ]
        report = calculate_pit38([], divs, [], mock_nbp, 2025)

        # Tylko dywidenda z 2025
        assert report.dividends_gross_pln == Decimal("400.00")  # 100 × 4.0

    def test_interest_wht_excluded(self, mock_nbp: MagicMock):
        """WHT od odsetek (INTEREST_WHT) NIE idzie do sekcji G."""
        divs = [_make_dividend(amount="100.00")]
        interest_wht = WithholdingTax(
            currency="USD",
            payment_date=date(2025, 6, 15),
            description="Interest WHT",
            amount=Decimal("-10.00"),
            wht_type=WhtType.INTEREST_WHT,
        )
        report = calculate_pit38([], divs, [interest_wht], mock_nbp, 2025)

        # WHT od odsetek nie jest odliczany w sekcji G
        assert report.g48_dividend_wht == Decimal("0.00")

    def test_multiple_dividends(self, mock_nbp: MagicMock):
        """Wiele dywidend sumuje się."""
        divs = [
            _make_dividend(amount="100.00"),
            _make_dividend(amount="50.00", payment_date=date(2025, 9, 15)),
            _make_dividend(amount="75.00", payment_date=date(2025, 12, 15)),
        ]
        report = calculate_pit38([], divs, [], mock_nbp, 2025)

        # (100 + 50 + 75) × 4.0 = 900 PLN
        assert report.dividends_gross_pln == Decimal("900.00")


# ────────────────────────────────────────────────────────────
# PIT/ZG -- per kraj
# ────────────────────────────────────────────────────────────

class TestPitZG:
    """PIT/ZG -- załącznik per kraj."""

    def test_single_country(self, mock_nbp: MagicMock):
        """Jeden kraj → jeden PIT/ZG."""
        lots = [_make_tax_lot(country="US")]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        assert len(report.pit_zg_entries) == 1
        us = report.pit_zg_entries[0]
        assert us.country_code == "US"
        assert us.country_name == "Stany Zjednoczone Ameryki"
        assert us.capital_gains_income > 0

    def test_multiple_countries(self, mock_nbp: MagicMock):
        """Wiele krajów (giełd) → osobny PIT/ZG per kraj."""
        lots = [
            _make_tax_lot(country="US", isin="US0378331005",
                          buy_cost_pln="10000", sell_proceeds_pln="15000"),
            _make_tax_lot(country="NL", isin="IE00B4L5Y983", symbol="IWDA",
                          listing_exchange="AEB",
                          buy_cost_pln="20000", sell_proceeds_pln="22000"),
            _make_tax_lot(country="GB", isin="GB00B03MLX29", symbol="RR.",
                          listing_exchange="LSE",
                          buy_cost_pln="5000", sell_proceeds_pln="3000"),
        ]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        assert len(report.pit_zg_entries) == 3
        countries = {e.country_code for e in report.pit_zg_entries}
        assert countries == {"US", "NL", "GB"}

        # GB ma stratę → capital_gains_income = 0
        gb = next(e for e in report.pit_zg_entries if e.country_code == "GB")
        assert gb.capital_gains_income == Decimal("0")

        # US ma zysk
        us = next(e for e in report.pit_zg_entries if e.country_code == "US")
        assert us.capital_gains_income == Decimal("5000.00")

    def test_no_dividends_in_pit_zg(self, mock_nbp: MagicMock):
        """Dywidendy NIE idą do PIT/ZG."""
        divs = [_make_dividend(amount="100.00")]
        report = calculate_pit38([], divs, [], mock_nbp, 2025)

        # Brak lotów → brak PIT/ZG
        assert len(report.pit_zg_entries) == 0

    def test_sorted_by_country(self, mock_nbp: MagicMock):
        """PIT/ZG posortowane po kodzie kraju."""
        lots = [
            _make_tax_lot(country="US", isin="US0378331005"),
            _make_tax_lot(country="IE", isin="IE00B4L5Y983", symbol="IWDA"),
        ]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        assert report.pit_zg_entries[0].country_code == "IE"
        assert report.pit_zg_entries[1].country_code == "US"


# ────────────────────────────────────────────────────────────
# Zaokrąglenia
# ────────────────────────────────────────────────────────────

class TestRounding:
    """Zaokrąglenia podatkowe."""

    def test_d31_floor(self, mock_nbp: MagicMock):
        """D.31 zaokrąglona w dół do pełnych PLN."""
        lots = [_make_tax_lot(buy_cost_pln="39999.01", sell_proceeds_pln="50000.00")]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        # Dochód = 10000.99 → floor = 10000
        assert report.d31_tax_base == Decimal("10000")

    def test_d35_rounded(self, mock_nbp: MagicMock):
        """D.35 zaokrąglona do pełnych PLN."""
        lots = [_make_tax_lot(buy_cost_pln="40000", sell_proceeds_pln="50000")]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        # 19% × 10000 = 1900.00 → 1900
        assert report.d35_tax_due == Decimal("1900")

    def test_g49_rounded(self, mock_nbp: MagicMock):
        """G.49 zaokrąglona do pełnych PLN."""
        divs = [_make_dividend(amount="100.00")]
        whts = [_make_wht(amount="-15.00")]
        report = calculate_pit38([], divs, whts, mock_nbp, 2025)

        # G.47 = 76, G.48 = 60, diff = 16 → 16
        assert report.g49_dividend_difference == Decimal("16")


# ────────────────────────────────────────────────────────────
# Suma końcowa
# ────────────────────────────────────────────────────────────

class TestTotalTax:
    """Suma końcowa podatku."""

    def test_total_tax(self, mock_nbp: MagicMock):
        """Total = D.35 + G.49."""
        lots = [_make_tax_lot(buy_cost_pln="40000", sell_proceeds_pln="50000")]
        divs = [_make_dividend(amount="100.00")]
        whts = [_make_wht(amount="-15.00")]
        report = calculate_pit38(lots, divs, whts, mock_nbp, 2025)

        assert report.total_tax_due == report.d35_tax_due + report.g49_dividend_difference

    def test_total_zero_when_loss(self, mock_nbp: MagicMock):
        """Rok ze stratą i bez dywidend → total = 0."""
        lots = [_make_tax_lot(buy_cost_pln="50000", sell_proceeds_pln="40000")]
        report = calculate_pit38(lots, [], [], mock_nbp, 2025)

        assert report.total_tax_due == Decimal("0")


# ────────────────────────────────────────────────────────────
# Decimal safety
# ────────────────────────────────────────────────────────────

class TestDecimalSafety:
    """Żadnych floatów w raporcie."""

    def test_all_decimal(self, mock_nbp: MagicMock):
        lots = [_make_tax_lot()]
        divs = [_make_dividend()]
        whts = [_make_wht()]
        report = calculate_pit38(lots, divs, whts, mock_nbp, 2025)

        decimal_fields = [
            report.c22_proceeds, report.c23_costs,
            report.c26_total_proceeds, report.c27_total_costs,
            report.c28_income, report.c29_loss,
            report.d30_prior_losses, report.d31_tax_base,
            report.d33_tax_calculated, report.d34_foreign_tax, report.d35_tax_due,
            report.dividends_gross_pln, report.g47_dividend_tax,
            report.g48_dividend_wht, report.g49_dividend_difference,
            report.total_tax_due,
        ]
        for val in decimal_fields:
            assert isinstance(val, Decimal), f"Oczekiwano Decimal, dostano {type(val)}: {val}"


# ────────────────────────────────────────────────────────────
# Integracja: pełny pipeline
# ────────────────────────────────────────────────────────────

class TestFullPipeline:
    """Integracja: parser → settlement → FIFO → tax."""

    def test_full_pipeline(self):
        """Pełny pipeline na prawdziwych danych IBKR."""
        fixture = Path(__file__).parent.parent.parent / "resources" / "U15663971_20241230_20251230.csv"
        if not fixture.exists():
            pytest.skip("Brak fixture CSV")

        from pit38.fifo.engine import run_fifo
        from pit38.parsers.ibkr_csv import parse_ibkr_csv
        from pit38.settlement.calculator import enrich_trades_with_settlement

        parsed = parse_ibkr_csv(fixture)
        enriched = enrich_trades_with_settlement(parsed.trades)

        # Mock NBP
        mock_nbp = MagicMock(spec=NBPClient)
        mock_nbp.get_rate.return_value = Decimal("4.0000")

        fifo_result = run_fifo(enriched, parsed.corporate_actions, mock_nbp, tax_year=2025)

        report = calculate_pit38(
            tax_lots=fifo_result.tax_lots,
            dividends=parsed.dividends,
            withholding_taxes=parsed.withholding_taxes,
            nbp_client=mock_nbp,
            tax_year=2025,
        )

        # Raport powinien mieć sensowne wartości
        assert report.tax_year == 2025
        assert report.c22_proceeds >= 0
        assert report.c23_costs >= 0
        assert isinstance(report.d35_tax_due, Decimal)
        assert len(report.pit_zg_entries) >= 1

        # Sprawdź spójność
        assert report.c26_total_proceeds == report.c22_proceeds
        assert report.c27_total_costs == report.c23_costs
        if report.c28_income > 0:
            assert report.c29_loss == 0
        if report.c29_loss > 0:
            assert report.c28_income == 0
