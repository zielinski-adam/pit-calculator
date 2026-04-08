"""
Parser IBKR Activity Statement CSV.

Parsuje sekcje: Trades, Financial Instrument Information, Corporate Actions,
Dividends, Withholding Tax. Ignoruje wiersze SubTotal/Total.

Settlement date NIE pochodzi z CSV -- jest obliczany później z exchange_calendars.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from loguru import logger

from pit38.models.corporate_action import CorporateAction
from pit38.models.dividend import Dividend, WithholdingTax
from pit38.models.enums import (
    AssetCategory,
    CorporateActionType,
    DividendType,
    WhtType,
)
from pit38.models.trade import InstrumentInfo, Trade


# Regex do parsowania opisów
_DIVIDEND_RE = re.compile(
    r"(\w+)\(([A-Z0-9]+)\)\s+"
    r"(Payment in Lieu of Dividend|Cash Dividend)"
)
_WHT_DIVIDEND_RE = re.compile(
    r"(\w+)\(([A-Z0-9]+)\)\s+.*?-\s*(\w+)\s+Tax"
)
_WHT_INTEREST_RE = re.compile(
    r"Withholding\s+@\s+\d+%\s+on\s+Credit\s+Interest"
)
_SPLIT_RE = re.compile(
    r"(\w+)\(([A-Z0-9]+)\)\s+Split\s+(\d+)\s+for\s+(\d+)"
)
_IBKR_DATETIME_FORMAT = "%Y-%m-%d, %H:%M:%S"
_IBKR_DATE_FORMAT = "%Y-%m-%d"


class IBKRParseResult:
    """Wynik parsowania IBKR CSV."""

    def __init__(self) -> None:
        self.trades: list[Trade] = []
        self.instruments: dict[str, InstrumentInfo] = {}  # klucz: symbol
        self.dividends: list[Dividend] = []
        self.withholding_taxes: list[WithholdingTax] = []
        self.corporate_actions: list[CorporateAction] = []
        self.account_name: str = ""
        self.account_id: str = ""
        self.period: str = ""
        self.base_currency: str = ""

    @property
    def stock_trades(self) -> list[Trade]:
        """Transakcje akcyjne (bez opcji)."""
        return [t for t in self.trades if t.asset_category == AssetCategory.STOCKS]

    @property
    def option_trades(self) -> list[Trade]:
        """Transakcje opcyjne."""
        return [t for t in self.trades if t.asset_category == AssetCategory.OPTIONS]

    @property
    def dividend_whts(self) -> list[WithholdingTax]:
        """WHT od dywidend (do sekcji G PIT-38)."""
        return [w for w in self.withholding_taxes if w.wht_type == WhtType.DIVIDEND_WHT]


def _trade_dedup_key(trade: Trade) -> tuple:
    """Klucz deduplikacji transakcji (IBKR CSV nie ma unikalnego ID)."""
    return (trade.symbol, trade.trade_datetime, trade.quantity, trade.price, trade.commission)


def _dividend_dedup_key(d: Dividend) -> tuple:
    """Klucz deduplikacji dywidendy."""
    return (d.symbol, d.isin, d.payment_date, d.amount, d.currency, d.dividend_type)


def _wht_dedup_key(w: WithholdingTax) -> tuple:
    """Klucz deduplikacji WHT."""
    return (w.currency, w.payment_date, w.amount, w.description)


def _ca_dedup_key(ca: CorporateAction) -> tuple:
    """Klucz deduplikacji corporate action."""
    return (ca.symbol, ca.isin, ca.action_date, ca.action_type, ca.quantity)


def merge_ibkr_results(results: list[IBKRParseResult]) -> IBKRParseResult:
    """Merguj wyniki z wielu plików CSV z deduplikacją."""
    if len(results) == 1:
        return results[0]

    merged = IBKRParseResult()

    # Metadane z pierwszego pliku
    first = results[0]
    merged.account_name = first.account_name
    merged.account_id = first.account_id
    merged.base_currency = first.base_currency
    merged.period = f"{first.period} (merged, {len(results)} plików)"

    # Deduplikacja trades
    seen_trades: set[tuple] = set()
    for r in results:
        for t in r.trades:
            key = _trade_dedup_key(t)
            if key not in seen_trades:
                seen_trades.add(key)
                merged.trades.append(t)

    # Deduplikacja dywidend
    seen_divs: set[tuple] = set()
    for r in results:
        for d in r.dividends:
            key = _dividend_dedup_key(d)
            if key not in seen_divs:
                seen_divs.add(key)
                merged.dividends.append(d)

    # Deduplikacja WHT
    seen_whts: set[tuple] = set()
    for r in results:
        for w in r.withholding_taxes:
            key = _wht_dedup_key(w)
            if key not in seen_whts:
                seen_whts.add(key)
                merged.withholding_taxes.append(w)

    # Deduplikacja corporate actions
    seen_cas: set[tuple] = set()
    for r in results:
        for ca in r.corporate_actions:
            key = _ca_dedup_key(ca)
            if key not in seen_cas:
                seen_cas.add(key)
                merged.corporate_actions.append(ca)

    # Merge instruments (późniejsze pliki nadpisują)
    for r in results:
        merged.instruments.update(r.instruments)

    # Sortuj trades chronologicznie
    merged.trades.sort(key=lambda t: t.trade_datetime)

    logger.info(
        f"Zmergowano {len(results)} plików: "
        f"{len(merged.trades)} transakcji (z {sum(len(r.trades) for r in results)} łącznie)"
    )

    return merged


def parse_ibkr_csvs(file_paths: list[Path]) -> IBKRParseResult:
    """Parsuj wiele plików CSV i zmerguj wyniki z deduplikacją."""
    results = [parse_ibkr_csv(fp) for fp in file_paths]
    return merge_ibkr_results(results)


def _parse_decimal(value: str) -> Decimal:
    """Parsuj string na Decimal, obsługując przecinki w liczbach (np. '1,000')."""
    try:
        return Decimal(value.replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _parse_datetime(value: str) -> datetime:
    """Parsuj datę/czas z formatu IBKR: '2025-03-10, 10:27:40'."""
    return datetime.strptime(value.strip().strip('"'), _IBKR_DATETIME_FORMAT)


def _parse_date(value: str) -> date:
    """Parsuj datę z formatu IBKR: '2025-03-10'."""
    return datetime.strptime(value.strip(), _IBKR_DATE_FORMAT).date()


def _parse_codes(value: str) -> list[str]:
    """Parsuj kody transakcji (np. 'C;P' → ['C', 'P'])."""
    if not value.strip():
        return []
    return [c.strip() for c in value.split(";") if c.strip()]


def _enrich_trade_with_instrument(
    trade_symbol: str,
    trade_asset_category: str,
    instruments: dict[str, InstrumentInfo],
) -> tuple[str, str, int, str | None, date | None, Decimal | None, str | None]:
    """
    Wzbogacenie trade'a o dane z Financial Instrument Information.

    Zwraca: (isin, listing_exchange, multiplier, underlying, expiry, strike, option_type)
    """
    def _result(info: InstrumentInfo) -> tuple[str, str, int, str | None, date | None, Decimal | None, str | None]:
        return info.isin, info.listing_exchange, info.multiplier, info.underlying, info.expiry, info.strike, info.option_type

    # Szukaj po symbolu z Trades (dla opcji: "NBIS 20MAR26 150 C")
    # W FII opcje mają inny format symbolu (np. "NBIS  260320C00150000")
    # Szukamy po opisie (Description) który jest taki sam jak symbol w Trades
    for info in instruments.values():
        if info.description == trade_symbol or info.symbol == trade_symbol:
            return _result(info)

    # Fallback: szukaj po pierwszym słowie (underlying) dla opcji
    if trade_asset_category == AssetCategory.OPTIONS:
        underlying = trade_symbol.split()[0] if " " in trade_symbol else trade_symbol
        for info in instruments.values():
            if info.underlying == underlying and info.asset_category == AssetCategory.OPTIONS:
                return _result(info)
        # Jeśli nie znaleziono opcji, spróbuj underlying jako stock
        if underlying in instruments:
            stock_info = instruments[underlying]
            return stock_info.isin, "CBOE", 100, underlying, None, None, None

    # Szukaj bezpośrednio po kluczu
    if trade_symbol in instruments:
        info = instruments[trade_symbol]
        return _result(info)

    # Fallback dla Treasury Bills: symbol w Trades ma suffix z oprocentowaniem
    # np. "912797KJ5 4.30699928%" → szukaj po "912797KJ5"
    if trade_asset_category == AssetCategory.TREASURY_BILLS:
        cusip = trade_symbol.split()[0] if " " in trade_symbol else trade_symbol
        if cusip in instruments:
            info = instruments[cusip]
            return _result(info)

    logger.warning(f"Brak danych instrumentu dla symbolu: {trade_symbol}")
    return "UNKNOWN", "UNKNOWN", 1, None, None, None, None


def parse_ibkr_csv(file_path: str | Path) -> IBKRParseResult:
    """
    Parsuj IBKR Activity Statement CSV.

    Obsługiwane sekcje:
    - Statement (metadane konta)
    - Account Information
    - Trades (akcje + opcje)
    - Financial Instrument Information (ISIN, giełda, multiplier)
    - Corporate Actions (splity)
    - Dividends
    - Withholding Tax

    Ignoruje: SubTotal, Total, Header wiersze.
    """
    result = IBKRParseResult()
    path = Path(file_path)

    with path.open(encoding="utf-8") as f:
        content = f.read()

    # CSV z IBKR ma różne formaty kolumn per sekcja -- parsujemy linia po linii
    reader = csv.reader(io.StringIO(content))

    # Najpierw: zbierz Financial Instrument Information (potrzebne do wzbogacenia trades)
    _parse_financial_instruments(content, result)

    for row in reader:
        if len(row) < 3:
            continue

        section = row[0].strip()
        row_type = row[1].strip()

        # Ignoruj nagłówki i podsumowania
        if row_type in {"Header", "SubTotal", "Total"}:
            # Ale wyciągnij metadane konta
            if section == "Statement" and row_type == "Data":
                _parse_statement_row(row, result)
            elif section == "Account Information" and row_type == "Data":
                _parse_account_info_row(row, result)
            continue

        if row_type != "Data":
            continue

        if section == "Statement":
            _parse_statement_row(row, result)
        elif section == "Account Information":
            _parse_account_info_row(row, result)
        elif section == "Trades":
            _parse_trade_row(row, result)
        elif section == "Corporate Actions":
            _parse_corporate_action_row(row, result)
        elif section == "Dividends":
            _parse_dividend_row(row, result)
        elif section == "Withholding Tax":
            _parse_wht_row(row, result)

    logger.info(
        f"Sparsowano CSV: {len(result.trades)} transakcji, "
        f"{len(result.instruments)} instrumentów, "
        f"{len(result.dividends)} dywidend, "
        f"{len(result.withholding_taxes)} WHT, "
        f"{len(result.corporate_actions)} corporate actions"
    )

    return result


def _parse_financial_instruments(content: str, result: IBKRParseResult) -> None:
    """Parsuj sekcję Financial Instrument Information -- osobno bo ma różne headery."""
    reader = csv.reader(io.StringIO(content))
    current_headers: list[str] = []

    for row in reader:
        if len(row) < 3:
            continue

        section = row[0].strip()
        row_type = row[1].strip()

        if section != "Financial Instrument Information":
            continue

        if row_type == "Header":
            current_headers = [h.strip() for h in row[2:]]
            continue

        if row_type != "Data":
            continue

        # Mapuj wartości na nagłówki
        values = row[2:]
        field_map = {}
        for i, header in enumerate(current_headers):
            if i < len(values):
                field_map[header] = values[i].strip()

        asset_category_str = field_map.get("Asset Category", "")
        symbol = field_map.get("Symbol", "").strip()
        description = field_map.get("Description", "")

        if not symbol:
            continue

        # Określ czy to akcje czy opcje
        try:
            asset_cat = AssetCategory(asset_category_str)
        except ValueError:
            logger.debug(f"Pominięto instrument z kategorią: {asset_category_str}")
            continue

        # ISIN -- pole Security ID (dla akcji) lub brak (dla opcji)
        isin = field_map.get("Security ID", "")

        # Dla opcji ISIN może nie być -- użyj ISIN underlying
        underlying = field_map.get("Underlying", None)

        # Multiplier
        multiplier_str = field_map.get("Multiplier", "1")
        try:
            multiplier = int(multiplier_str)
        except ValueError:
            multiplier = 1

        # Conid
        conid_str = field_map.get("Conid", "0")
        try:
            conid = int(conid_str)
        except ValueError:
            conid = 0

        # Pola opcyjne
        expiry = None
        strike = None
        option_type = None
        if asset_cat == AssetCategory.OPTIONS:
            expiry_str = field_map.get("Expiry", "")
            if expiry_str:
                try:
                    expiry = _parse_date(expiry_str)
                except ValueError:
                    pass
            strike_str = field_map.get("Strike", "")
            if strike_str:
                try:
                    strike = Decimal(strike_str)
                except (InvalidOperation, ValueError):
                    pass
            option_type = field_map.get("Type", None)

        # Listing Exch: dla Treasury Bills IBKR wstawia "BILL" w pole Underlying,
        # a Listing Exch jest puste -- naprawiamy tutaj
        listing_exch = field_map.get("Listing Exch", "").strip()
        if not listing_exch and asset_cat == AssetCategory.TREASURY_BILLS:
            listing_exch = "BILL"

        info = InstrumentInfo(
            asset_category=asset_cat,
            symbol=symbol,
            description=description,
            conid=conid,
            isin=isin if isin else (f"OPT-{conid}" if conid else "UNKNOWN"),
            listing_exchange=listing_exch or "UNKNOWN",
            multiplier=multiplier,
            underlying=underlying,
            instrument_type=field_map.get("Type", ""),
            expiry=expiry,
            strike=strike,
            option_type=option_type,
        )

        # Klucz: symbol z FII (może różnić się od symbolu w Trades dla opcji)
        result.instruments[symbol] = info
        # Dodaj też po opisie (Description) jako alternatywny klucz
        if description and description != symbol:
            result.instruments[description] = info

    logger.debug(f"Sparsowano {len(result.instruments)} instrumentów z Financial Instrument Information")


def _parse_statement_row(row: list[str], result: IBKRParseResult) -> None:
    """Parsuj wiersz Statement (metadane)."""
    if len(row) < 4:
        return
    field_name = row[2].strip()
    field_value = row[3].strip()

    if field_name == "Period":
        result.period = field_value
    elif field_name == "Title":
        pass  # "Activity Statement"


def _parse_account_info_row(row: list[str], result: IBKRParseResult) -> None:
    """Parsuj wiersz Account Information."""
    if len(row) < 4:
        return
    field_name = row[2].strip()
    field_value = row[3].strip()

    if field_name == "Name":
        result.account_name = field_value
    elif field_name == "Account":
        result.account_id = field_value
    elif field_name == "Base Currency":
        result.base_currency = field_value


def _parse_trade_row(row: list[str], result: IBKRParseResult) -> None:
    """
    Parsuj wiersz Trades.

    Format CSV:
    Trades,Data,Order,{Asset Category},{Currency},{Symbol},{Date/Time},{Quantity},
    {T. Price},{C. Price},{Proceeds},{Comm/Fee},{Basis},{Realized P/L},{MTM P/L},{Code}
    """
    if len(row) < 16:
        return

    data_discriminator = row[2].strip()
    if data_discriminator != "Order":
        return  # Pomiń SubTotal, Total

    asset_category_str = row[3].strip()
    try:
        asset_cat = AssetCategory(asset_category_str)
    except ValueError:
        logger.debug(f"Pominięto trade z kategorią: {asset_category_str}")
        return

    currency = row[4].strip()
    symbol = row[5].strip()
    datetime_str = row[6].strip()
    quantity_str = row[7].strip()
    price_str = row[8].strip()
    # row[9] = C. Price (ignorujemy)
    proceeds_str = row[10].strip()
    commission_str = row[11].strip()
    # row[12] = Basis, row[13] = Realized P/L, row[14] = MTM P/L
    code_str = row[15].strip() if len(row) > 15 else ""

    try:
        trade_dt = _parse_datetime(datetime_str)
    except ValueError:
        logger.warning(f"Nieprawidłowy format daty: {datetime_str}")
        return

    # Wzbogać o dane z Financial Instrument Information
    isin, listing_exchange, multiplier, underlying, expiry, strike, option_type = (
        _enrich_trade_with_instrument(symbol, asset_category_str, result.instruments)
    )

    trade = Trade(
        symbol=symbol,
        isin=isin,
        asset_category=asset_cat,
        currency=currency,
        listing_exchange=listing_exchange,
        trade_datetime=trade_dt,
        trade_date=trade_dt.date(),
        quantity=_parse_decimal(quantity_str),
        price=_parse_decimal(price_str),
        proceeds=_parse_decimal(proceeds_str),
        commission=_parse_decimal(commission_str),
        multiplier=multiplier,
        underlying=underlying,
        expiry=expiry,
        strike=strike,
        option_type=option_type,
        codes=_parse_codes(code_str),
    )

    result.trades.append(trade)


def _parse_corporate_action_row(row: list[str], result: IBKRParseResult) -> None:
    """
    Parsuj wiersz Corporate Actions.

    Format: Corporate Actions,Data,{Asset Category},{Currency},{Report Date},
    {Date/Time},{Description},{Quantity},{Proceeds},{Value},{Realized P/L},{Code}
    """
    if len(row) < 8:
        return

    asset_category = row[2].strip()
    currency = row[3].strip()
    report_date_str = row[4].strip()
    datetime_str = row[5].strip()
    description = row[6].strip()
    quantity_str = row[7].strip()

    # Parsuj opis splitu
    split_match = _SPLIT_RE.search(description)
    if not split_match:
        logger.debug(f"Pominięto corporate action (nie-split): {description}")
        return

    symbol = split_match.group(1)
    isin = split_match.group(2)
    ratio_to = int(split_match.group(3))
    ratio_from = int(split_match.group(4))

    try:
        action_dt = _parse_datetime(datetime_str)
        report_dt = _parse_date(report_date_str)
    except ValueError:
        logger.warning(f"Nieprawidłowy format daty w corporate action: {datetime_str}")
        return

    ca = CorporateAction(
        asset_category=asset_category,
        currency=currency,
        report_date=report_dt,
        action_datetime=action_dt,
        action_date=action_dt.date(),
        description=description,
        symbol=symbol,
        isin=isin,
        quantity=_parse_decimal(quantity_str),
        action_type=CorporateActionType.SPLIT,
        ratio_from=ratio_from,
        ratio_to=ratio_to,
    )

    result.corporate_actions.append(ca)
    logger.info(f"Split: {symbol} {ratio_to}:{ratio_from} ({isin})")


def _parse_dividend_row(row: list[str], result: IBKRParseResult) -> None:
    """
    Parsuj wiersz Dividends.

    Format: Dividends,Data,{Currency},{Date},{Description},{Amount}
    """
    if len(row) < 6:
        return

    currency = row[2].strip()
    date_str = row[3].strip()
    description = row[4].strip()
    amount_str = row[5].strip()

    # Ignoruj wiersze Total
    if currency in {"Total", "Total in PLN"}:
        return

    # Parsuj opis -- wyciągnij symbol i ISIN
    match = _DIVIDEND_RE.search(description)
    if not match:
        logger.debug(f"Pominięto dywidendę (nierozpoznany format): {description}")
        return

    symbol = match.group(1)
    isin = match.group(2)
    div_type_str = match.group(3)

    div_type = (
        DividendType.PAYMENT_IN_LIEU
        if "Payment in Lieu" in div_type_str
        else DividendType.CASH_DIVIDEND
    )

    try:
        payment_dt = _parse_date(date_str)
    except ValueError:
        logger.warning(f"Nieprawidłowy format daty dywidendy: {date_str}")
        return

    dividend = Dividend(
        currency=currency,
        payment_date=payment_dt,
        symbol=symbol,
        isin=isin,
        description=description,
        amount=_parse_decimal(amount_str),
        dividend_type=div_type,
    )

    result.dividends.append(dividend)


def _parse_wht_row(row: list[str], result: IBKRParseResult) -> None:
    """
    Parsuj wiersz Withholding Tax.

    Format: Withholding Tax,Data,{Currency},{Date},{Description},{Amount},{Code}
    """
    if len(row) < 6:
        return

    currency = row[2].strip()
    date_str = row[3].strip()
    description = row[4].strip()
    amount_str = row[5].strip()

    # Ignoruj wiersze Total
    if currency in {"Total", "Total in PLN", "Total Withholding Tax in PLN"}:
        return

    try:
        payment_dt = _parse_date(date_str)
    except ValueError:
        logger.warning(f"Nieprawidłowy format daty WHT: {date_str}")
        return

    # Określ typ WHT
    if _WHT_INTEREST_RE.search(description):
        # WHT na odsetki -- PIT-36, out of scope
        wht = WithholdingTax(
            currency=currency,
            payment_date=payment_dt,
            description=description,
            amount=_parse_decimal(amount_str),
            wht_type=WhtType.INTEREST_WHT,
        )
    else:
        # WHT na dywidendy -- sekcja G PIT-38
        div_match = _WHT_DIVIDEND_RE.search(description)
        symbol = div_match.group(1) if div_match else None
        isin = div_match.group(2) if div_match else None

        wht = WithholdingTax(
            currency=currency,
            payment_date=payment_dt,
            symbol=symbol,
            isin=isin,
            description=description,
            amount=_parse_decimal(amount_str),
            wht_type=WhtType.DIVIDEND_WHT,
        )

    result.withholding_taxes.append(wht)
