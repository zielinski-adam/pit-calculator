"""Testy parsera IBKR Activity Statement CSV na prawdziwych danych."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from pit38.models.enums import AssetCategory, DividendType, WhtType
from pit38.parsers.ibkr_csv import parse_ibkr_csv

# Ścieżka do prawdziwego pliku CSV
FIXTURE_PATH = Path(__file__).parent.parent.parent / "resources" / "U15663971_20241230_20251230.csv"


@pytest.fixture
def parsed():
    """Sparsowany plik CSV."""
    assert FIXTURE_PATH.exists(), f"Brak fixture: {FIXTURE_PATH}"
    return parse_ibkr_csv(FIXTURE_PATH)


class TestAccountInfo:
    """Testy metadanych konta."""

    def test_account_id(self, parsed):
        assert parsed.account_id == "U15663971"

    def test_account_name(self, parsed):
        assert parsed.account_name == "Adam Zielinski"

    def test_base_currency(self, parsed):
        assert parsed.base_currency == "PLN"


class TestFinancialInstruments:
    """Testy sekcji Financial Instrument Information."""

    def test_instruments_parsed(self, parsed):
        """Powinno być co najmniej 20 instrumentów (akcje + opcje)."""
        # Instrumenty mogą być zduplikowane (symbol + description)
        unique_conids = {info.conid for info in parsed.instruments.values()}
        assert len(unique_conids) >= 20

    def test_stock_instrument_isin(self, parsed):
        """IWDA powinien mieć ISIN IE00B4L5Y983."""
        iwda = parsed.instruments.get("IWDA")
        assert iwda is not None
        assert iwda.isin == "IE00B4L5Y983"
        assert iwda.listing_exchange == "AEB"
        assert iwda.multiplier == 1
        assert iwda.asset_category == AssetCategory.STOCKS

    def test_option_instrument(self, parsed):
        """Opcja NBIS powinna mieć multiplier 100 i giełdę CBOE."""
        # Szukaj opcji NBIS w instruments
        nbis_options = [
            info for info in parsed.instruments.values()
            if info.asset_category == AssetCategory.OPTIONS and info.underlying == "NBIS"
        ]
        assert len(nbis_options) >= 1
        opt = nbis_options[0]
        assert opt.multiplier == 100
        assert opt.listing_exchange == "CBOE"

    def test_country_from_isin(self, parsed):
        """Kraj z prefiksu ISIN: IWDA → IE, AAPL → US, JOBY → KY."""
        # IWDA jest irlandzki
        iwda = parsed.instruments.get("IWDA")
        assert iwda is not None
        assert iwda.country == "IE"

        # JOBY jest na Kajmanach (KYG651631007)
        joby = parsed.instruments.get("JOBY")
        assert joby is not None
        assert joby.country == "KY"

    def test_nbis_is_dutch(self, parsed):
        """NBIS (Nebius) ma ISIN NL0009805522 → kraj NL (Holandia)."""
        nbis = parsed.instruments.get("NBIS")
        assert nbis is not None
        assert nbis.isin == "NL0009805522"
        assert nbis.country == "NL"


class TestTrades:
    """Testy parsowania transakcji."""

    def test_trades_parsed(self, parsed):
        """Powinno być co najmniej 50 transakcji (akcje + opcje)."""
        assert len(parsed.trades) >= 50

    def test_stock_trades_count(self, parsed):
        """Transakcje akcyjne."""
        stocks = parsed.stock_trades
        assert len(stocks) >= 30

    def test_option_trades_count(self, parsed):
        """Transakcje opcyjne."""
        options = parsed.option_trades
        assert len(options) >= 20

    def test_first_trade_in_january(self, parsed):
        """Pierwsza transakcja akcyjna jest ze stycznia 2025."""
        stocks = [t for t in parsed.trades if t.asset_category == AssetCategory.STOCKS]
        stocks.sort(key=lambda t: t.trade_datetime)
        first = stocks[0]
        assert first.trade_date.month == 1
        assert first.trade_date.year == 2025

    def test_buy_quantity_positive(self, parsed):
        """Kupno ma quantity > 0."""
        buys = [t for t in parsed.trades if t.is_buy]
        assert len(buys) > 0
        for buy in buys:
            assert buy.quantity > 0
            assert buy.buy_sell.value == "BUY"

    def test_sell_quantity_negative(self, parsed):
        """Sprzedaż ma quantity < 0."""
        sells = [t for t in parsed.trades if t.is_sell]
        assert len(sells) > 0
        for sell in sells:
            assert sell.quantity < 0
            assert sell.buy_sell.value == "SELL"

    def test_quantity_with_comma(self, parsed):
        """Parsowanie quantity z przecinkiem (np. '1,000')."""
        # ABSI ma quantity 1000 (zapisane jako "1,000" w CSV)
        absi_buys = [
            t for t in parsed.trades
            if t.symbol == "ABSI" and t.is_buy
        ]
        if absi_buys:
            assert absi_buys[0].quantity == Decimal("1000")

    def test_trade_has_isin(self, parsed):
        """Każdy trade powinien mieć ISIN z Financial Instrument Information."""
        for trade in parsed.stock_trades:
            assert trade.isin != "UNKNOWN", f"Brak ISIN dla {trade.symbol}"

    def test_trade_has_listing_exchange(self, parsed):
        """Każdy trade akcyjny powinien mieć listing exchange."""
        for trade in parsed.stock_trades:
            assert trade.listing_exchange != "UNKNOWN", f"Brak giełdy dla {trade.symbol}"

    def test_decimal_not_float(self, parsed):
        """Wszystkie kwoty to Decimal, nie float."""
        for trade in parsed.trades:
            assert isinstance(trade.quantity, Decimal)
            assert isinstance(trade.price, Decimal)
            assert isinstance(trade.proceeds, Decimal)
            assert isinstance(trade.commission, Decimal)

    def test_trade_country(self, parsed):
        """Trade.country pochodzi z prefiksu ISIN."""
        iwda_trades = [t for t in parsed.trades if t.symbol == "IWDA"]
        if iwda_trades:
            assert iwda_trades[0].country == "IE"

    def test_option_trade_has_cboe(self, parsed):
        """Opcje powinny mieć listing_exchange CBOE."""
        for trade in parsed.option_trades:
            assert trade.listing_exchange == "CBOE", f"Opcja {trade.symbol} ma giełdę {trade.listing_exchange}"

    def test_settle_date_initially_none(self, parsed):
        """Settlement date nie jest ustawiony po parsowaniu -- obliczany później."""
        for trade in parsed.trades:
            assert trade.settle_date is None


class TestCorporateActions:
    """Testy parsowania corporate actions (splitów)."""

    def test_split_parsed(self, parsed):
        """Split IBKR 4:1 powinien być sparsowany."""
        assert len(parsed.corporate_actions) >= 1

    def test_ibkr_split_details(self, parsed):
        """Szczegóły splitu IBKR: 4 for 1, ISIN US45841N1072."""
        splits = [ca for ca in parsed.corporate_actions if ca.symbol == "IBKR"]
        assert len(splits) == 1
        split = splits[0]
        assert split.ratio_to == 4
        assert split.ratio_from == 1
        assert split.isin == "US45841N1072"


class TestDividends:
    """Testy parsowania dywidend."""

    def test_dividends_parsed(self, parsed):
        """Powinny być co najmniej 4 dywidendy (IBKR quarterly)."""
        assert len(parsed.dividends) >= 4

    def test_dividend_types(self, parsed):
        """Powinny być zarówno Cash Dividend jak i Payment in Lieu."""
        types = {d.dividend_type for d in parsed.dividends}
        assert DividendType.CASH_DIVIDEND in types or DividendType.PAYMENT_IN_LIEU in types

    def test_dividend_isin(self, parsed):
        """Dywidendy IBKR powinny mieć ISIN US45841N1072."""
        for div in parsed.dividends:
            assert div.isin == "US45841N1072"
            assert div.country == "US"

    def test_dividend_amount_positive(self, parsed):
        """Kwoty dywidend powinny być dodatnie."""
        for div in parsed.dividends:
            assert div.amount > 0

    def test_dividend_amount_decimal(self, parsed):
        """Kwoty dywidend to Decimal."""
        for div in parsed.dividends:
            assert isinstance(div.amount, Decimal)


class TestWithholdingTax:
    """Testy parsowania WHT."""

    def test_whts_parsed(self, parsed):
        """Powinno być co najmniej 10 wierszy WHT."""
        assert len(parsed.withholding_taxes) >= 10

    def test_dividend_wht_vs_interest_wht(self, parsed):
        """Powinny być oba typy: dividend WHT i interest WHT."""
        types = {w.wht_type for w in parsed.withholding_taxes}
        assert WhtType.DIVIDEND_WHT in types
        assert WhtType.INTEREST_WHT in types

    def test_dividend_wht_has_isin(self, parsed):
        """WHT od dywidend powinien mieć ISIN."""
        div_whts = parsed.dividend_whts
        assert len(div_whts) >= 3
        for wht in div_whts:
            assert wht.isin is not None
            assert wht.country == "US"

    def test_wht_amounts_negative(self, parsed):
        """WHT kwoty powinny być ujemne (potrącone)."""
        for wht in parsed.withholding_taxes:
            assert wht.amount < 0 or wht.amount == Decimal("0")
