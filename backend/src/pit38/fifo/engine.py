"""
Silnik FIFO multi-year z settlement date ordering.

Klucz sortowania: (settle_date, trade_date)
Osobny koszyk per instrument (symbol + asset_category).
Obsługa opcji: multiplier, wygaśnięcie (Ep), exercise (Ex), assignment (A),
               short baskets (sell-to-open / buy-to-close).
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from pit38.models.corporate_action import CorporateAction
from pit38.models.enums import AssetCategory
from pit38.models.tax_lot import TaxLot
from pit38.models.trade import Trade
from pit38.nbp.client import NBPClient
from pit38.settlement.calculator import compute_nbp_rate_date

logger = logging.getLogger(__name__)


@dataclass
class OpenLot:
    """
    Otwarty lot kupna w kolejce FIFO.

    Mutable -- quantity zmniejsza się przy dopasowywaniu do sprzedaży,
    i zmienia się przy splitach.
    """
    trade: Trade
    remaining_quantity: Decimal  # ile zostało (zawsze dodatnia)
    original_quantity: Decimal   # oryginalna ilość kupna (do proporcji prowizji)
    price_per_unit: Decimal      # cena per unit (zmienia się przy splitach)

    @property
    def commission_ratio(self) -> Decimal:
        """Proporcja prowizji do przydzielenia: remaining / original."""
        if self.original_quantity == 0:
            return Decimal("0")
        return self.remaining_quantity / self.original_quantity


@dataclass
class FIFOResult:
    """Wynik przetwarzania FIFO."""
    tax_lots: list[TaxLot] = field(default_factory=list)
    open_positions: dict[str, list[OpenLot]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def run_fifo(
    trades: list[Trade],
    corporate_actions: list[CorporateAction],
    nbp_client: NBPClient,
    tax_year: int | None = None,
) -> FIFOResult:
    """
    Uruchom silnik FIFO na liście transakcji.

    Args:
        trades: Lista transakcji z ustawionym settle_date
        corporate_actions: Lista zdarzeń korporacyjnych (splity)
        nbp_client: Klient NBP do pobierania kursów
        tax_year: Jeśli podany, zwróć TaxLots tylko dla tego roku podatkowego.
                  None = wszystkie lata.

    Returns:
        FIFOResult z zamkniętymi pozycjami i otwartymi lotami
    """
    result = FIFOResult()

    # Walidacja: wszystkie trades muszą mieć settle_date
    for t in trades:
        if t.settle_date is None:
            raise ValueError(f"Trade {t.symbol} {t.trade_date} nie ma settle_date")

    # Sortuj transakcje po (settle_date, trade_date)
    sorted_trades = sorted(trades, key=lambda t: (t.settle_date, t.trade_date))

    # Sortuj corporate actions po dacie
    sorted_actions = sorted(corporate_actions, key=lambda ca: ca.action_date)

    # Kolejki FIFO per instrument (klucz = symbol)
    baskets: dict[str, deque[OpenLot]] = defaultdict(deque)

    # Osobne koszyki dla krótkich pozycji opcyjnych (sell-to-open)
    short_baskets: dict[str, deque[OpenLot]] = defaultdict(deque)

    # Indeks corporate actions do przetworzenia
    action_idx = 0

    for trade in sorted_trades:
        # Aplikuj corporate actions z datą <= trade.settle_date
        while action_idx < len(sorted_actions):
            action = sorted_actions[action_idx]
            if action.action_date <= trade.settle_date:
                _apply_corporate_action(action, baskets, result)
                action_idx += 1
            else:
                break

        basket_key = _basket_key(trade)

        # Routing opcji -- osobna logika dla zdarzeń opcyjnych
        if trade.is_option and trade.is_expiration:
            _process_option_expiration(
                trade, baskets, short_baskets, basket_key,
                nbp_client, result, tax_year,
            )
        elif trade.is_option and trade.is_exercise:
            _process_exercise(
                trade, baskets, basket_key, nbp_client, result,
            )
        elif trade.is_option and trade.is_assignment:
            _process_assignment(
                trade, short_baskets, baskets, basket_key,
                nbp_client, result, tax_year,
            )
        elif trade.is_option and "O" in trade.codes and trade.is_sell:
            # Sell-to-open: wystawienie opcji (short)
            _process_short_open(trade, short_baskets, basket_key)
        elif trade.is_option and "C" in trade.codes and trade.is_buy:
            # Buy-to-close: zamknięcie krótkiej pozycji opcyjnej
            _process_short_close(
                trade, short_baskets, basket_key, nbp_client, result, tax_year,
            )
        elif trade.is_buy:
            _process_buy(trade, baskets, basket_key)
        elif trade.is_sell:
            _process_sell(trade, baskets, basket_key, nbp_client, result, tax_year)

    # Aplikuj pozostałe corporate actions
    while action_idx < len(sorted_actions):
        _apply_corporate_action(sorted_actions[action_idx], baskets, result)
        action_idx += 1

    # Zapisz otwarte pozycje (long + short)
    for key, basket in baskets.items():
        if basket:
            result.open_positions[key] = list(basket)
    for key, basket in short_baskets.items():
        if basket:
            result.open_positions[f"{key}:SHORT"] = list(basket)

    return result


def _basket_key(trade: Trade) -> str:
    """Klucz koszyka FIFO -- osobny per instrument."""
    return trade.symbol


def _process_buy(
    trade: Trade,
    baskets: dict[str, deque[OpenLot]],
    basket_key: str,
) -> None:
    """Dodaj lot kupna na koniec kolejki FIFO."""
    lot = OpenLot(
        trade=trade,
        remaining_quantity=abs(trade.quantity),
        original_quantity=abs(trade.quantity),
        price_per_unit=trade.price,
    )
    baskets[basket_key].append(lot)


def _process_sell(
    trade: Trade,
    baskets: dict[str, deque[OpenLot]],
    basket_key: str,
    nbp_client: NBPClient,
    result: FIFOResult,
    tax_year: int | None,
) -> None:
    """Dopasuj sprzedaż do lotów kupna (FIFO)."""
    basket = baskets[basket_key]
    sell_quantity = abs(trade.quantity)

    if not basket:
        result.warnings.append(
            f"Short sell {trade.symbol} {trade.trade_date}: "
            f"brak otwartych pozycji do dopasowania"
        )
        return

    # Sell NBP rate -- oblicz raz
    sell_nbp_date = compute_nbp_rate_date(trade.settle_date)
    sell_nbp_rate = nbp_client.get_rate(trade.currency, sell_nbp_date)

    while sell_quantity > 0 and basket:
        lot = basket[0]

        if lot.remaining_quantity <= sell_quantity:
            # Cały lot zużyty
            matched_qty = lot.remaining_quantity
            sell_quantity -= matched_qty

            # Proporcja prowizji kupna
            buy_commission_share = trade.commission  # będzie proporcjonalne poniżej
            buy_comm = _proportional_commission(
                lot.trade.commission, matched_qty, lot.original_quantity
            )

            # Proporcja prowizji sprzedaży
            sell_comm = _proportional_commission(
                trade.commission, matched_qty, abs(trade.quantity)
            )

            tax_lot = _create_tax_lot(
                buy_lot=lot,
                sell_trade=trade,
                matched_qty=matched_qty,
                buy_commission=buy_comm,
                sell_commission=sell_comm,
                sell_nbp_rate_date=sell_nbp_date,
                sell_nbp_rate=sell_nbp_rate,
                nbp_client=nbp_client,
            )

            if tax_year is None or tax_lot.tax_year == tax_year:
                result.tax_lots.append(tax_lot)

            basket.popleft()
        else:
            # Częściowe dopasowanie
            matched_qty = sell_quantity
            lot.remaining_quantity -= matched_qty
            sell_quantity = Decimal("0")

            buy_comm = _proportional_commission(
                lot.trade.commission, matched_qty, lot.original_quantity
            )
            sell_comm = _proportional_commission(
                trade.commission, matched_qty, abs(trade.quantity)
            )

            tax_lot = _create_tax_lot(
                buy_lot=lot,
                sell_trade=trade,
                matched_qty=matched_qty,
                buy_commission=buy_comm,
                sell_commission=sell_comm,
                sell_nbp_rate_date=sell_nbp_date,
                sell_nbp_rate=sell_nbp_rate,
                nbp_client=nbp_client,
            )

            if tax_year is None or tax_lot.tax_year == tax_year:
                result.tax_lots.append(tax_lot)

    if sell_quantity > 0:
        result.warnings.append(
            f"Brak wystarczających lotów dla {trade.symbol} {trade.trade_date}: "
            f"niedobór {sell_quantity}"
        )


def _proportional_commission(
    total_commission: Decimal,
    matched_qty: Decimal,
    total_qty: Decimal,
) -> Decimal:
    """Prowizja proporcjonalna do dopasowanej ilości."""
    if total_qty == 0:
        return Decimal("0")
    return total_commission * matched_qty / total_qty


def _create_tax_lot(
    buy_lot: OpenLot,
    sell_trade: Trade,
    matched_qty: Decimal,
    buy_commission: Decimal,
    sell_commission: Decimal,
    sell_nbp_rate_date: date,
    sell_nbp_rate: Decimal,
    nbp_client: NBPClient,
) -> TaxLot:
    """Utwórz TaxLot z dopasowania buy-sell."""
    buy_trade = buy_lot.trade

    # Buy NBP rate
    buy_nbp_date = compute_nbp_rate_date(buy_trade.settle_date)
    buy_nbp_rate = nbp_client.get_rate(buy_trade.currency, buy_nbp_date)

    # Oblicz kwoty w PLN
    # Koszt kupna: (cena × ilość × mnożnik + |prowizja|) × kurs NBP
    # Prowizja jest ujemna, więc bierzemy wartość bezwzględną
    # Mnożnik: 1 dla akcji, 100 dla opcji (IBKR price = premia per share)
    multiplier = Decimal(buy_trade.multiplier)
    buy_amount = buy_lot.price_per_unit * matched_qty * multiplier
    buy_cost_pln = (buy_amount + abs(buy_commission)) * buy_nbp_rate

    # Przychód sprzedaży: (cena × ilość × mnożnik - |prowizja|) × kurs NBP
    sell_multiplier = Decimal(sell_trade.multiplier)
    sell_amount = sell_trade.price * matched_qty * sell_multiplier
    sell_proceeds_pln = (sell_amount - abs(sell_commission)) * sell_nbp_rate

    profit_loss = sell_proceeds_pln - buy_cost_pln

    return TaxLot(
        symbol=sell_trade.symbol,
        isin=sell_trade.isin,
        country=sell_trade.country,
        listing_exchange=sell_trade.listing_exchange,
        asset_category=sell_trade.asset_category,
        currency=sell_trade.currency,
        multiplier=sell_trade.multiplier,
        buy_trade_date=buy_trade.trade_date,
        buy_settle_date=buy_trade.settle_date,
        buy_nbp_rate_date=buy_nbp_date,
        buy_nbp_rate=buy_nbp_rate,
        buy_price=buy_lot.price_per_unit,
        buy_quantity=matched_qty,
        buy_commission=buy_commission,
        buy_cost_pln=buy_cost_pln,
        sell_trade_date=sell_trade.trade_date,
        sell_settle_date=sell_trade.settle_date,
        sell_nbp_rate_date=sell_nbp_rate_date,
        sell_nbp_rate=sell_nbp_rate,
        sell_price=sell_trade.price,
        sell_quantity=matched_qty,
        sell_commission=sell_commission,
        sell_proceeds_pln=sell_proceeds_pln,
        profit_loss_pln=profit_loss,
    )


# ────────────────────────────────────────────────────────────
# Obsługa zdarzeń opcyjnych
# ────────────────────────────────────────────────────────────


def _process_option_expiration(
    trade: Trade,
    baskets: dict[str, deque[OpenLot]],
    short_baskets: dict[str, deque[OpenLot]],
    basket_key: str,
    nbp_client: NBPClient,
    result: FIFOResult,
    tax_year: int | None,
) -> None:
    """
    Wygaśnięcie opcji (kod Ep).

    Buyer (qty < 0): opcja wygasa bezwartościowo → strata = koszt premii.
    Writer (qty > 0): opcja wygasa → zysk = otrzymana premia.
    """
    if trade.is_sell:
        # Buyer: long option expires → zamknięcie z ceną 0
        # IBKR wysyła qty < 0, price = 0 → standardowa ścieżka sell
        _process_sell(trade, baskets, basket_key, nbp_client, result, tax_year)
    else:
        # Writer: short option expires → zamknięcie krótkiej pozycji z ceną 0
        _process_short_close(
            trade, short_baskets, basket_key, nbp_client, result, tax_year,
        )


def _process_exercise(
    trade: Trade,
    baskets: dict[str, deque[OpenLot]],
    basket_key: str,
    nbp_client: NBPClient,
    result: FIFOResult,
) -> None:
    """
    Wykonanie opcji przez kupującego (kod Ex, qty < 0 dla call).

    Opcja znika z koszyka opcyjnego, powstaje syntetyczny lot akcji
    z cost basis = strike + premium. Brak zdarzenia podatkowego.
    """
    basket = baskets[basket_key]
    exercise_qty = abs(trade.quantity)

    if not basket:
        result.warnings.append(
            f"Exercise {trade.symbol} {trade.trade_date}: "
            f"brak otwartych pozycji opcyjnych do dopasowania"
        )
        return

    if trade.strike is None:
        result.warnings.append(
            f"Exercise {trade.symbol} {trade.trade_date}: "
            f"brak strike price — nie można obliczyć cost basis akcji"
        )
        return

    underlying = trade.underlying
    if not underlying:
        result.warnings.append(
            f"Exercise {trade.symbol} {trade.trade_date}: "
            f"brak underlying symbol"
        )
        return

    multiplier = Decimal(trade.multiplier)

    while exercise_qty > 0 and basket:
        lot = basket[0]

        if lot.remaining_quantity <= exercise_qty:
            matched_qty = lot.remaining_quantity
            exercise_qty -= matched_qty
            premium_per_share = lot.price_per_unit

            # Prowizja opcji przenosi się proporcjonalnie do lotu akcji
            opt_commission = _proportional_commission(
                lot.trade.commission, matched_qty, lot.original_quantity
            )

            # Cost basis per share = strike + premium
            stock_cost_per_share = trade.strike + premium_per_share

            # Syntetyczny lot akcji: ilość = kontrakty × mnożnik
            stock_qty = matched_qty * multiplier

            # Stwórz syntetyczny Trade akcji do przechowywania w OpenLot
            synthetic_trade = Trade(
                symbol=underlying,
                isin=trade.isin,
                asset_category=AssetCategory.STOCKS,
                currency=trade.currency,
                listing_exchange=trade.listing_exchange,
                trade_datetime=trade.trade_datetime,
                trade_date=trade.trade_date,
                settle_date=trade.settle_date,
                quantity=stock_qty,
                price=stock_cost_per_share,
                proceeds=-(stock_qty * stock_cost_per_share),
                commission=opt_commission,
                multiplier=1,
                underlying=None,
            )

            stock_lot = OpenLot(
                trade=synthetic_trade,
                remaining_quantity=stock_qty,
                original_quantity=stock_qty,
                price_per_unit=stock_cost_per_share,
            )
            baskets[underlying].append(stock_lot)

            basket.popleft()
        else:
            matched_qty = exercise_qty
            lot.remaining_quantity -= matched_qty
            exercise_qty = Decimal("0")
            premium_per_share = lot.price_per_unit

            opt_commission = _proportional_commission(
                lot.trade.commission, matched_qty, lot.original_quantity
            )

            stock_cost_per_share = trade.strike + premium_per_share
            stock_qty = matched_qty * multiplier

            synthetic_trade = Trade(
                symbol=underlying,
                isin=trade.isin,
                asset_category=AssetCategory.STOCKS,
                currency=trade.currency,
                listing_exchange=trade.listing_exchange,
                trade_datetime=trade.trade_datetime,
                trade_date=trade.trade_date,
                settle_date=trade.settle_date,
                quantity=stock_qty,
                price=stock_cost_per_share,
                proceeds=-(stock_qty * stock_cost_per_share),
                commission=opt_commission,
                multiplier=1,
                underlying=None,
            )

            stock_lot = OpenLot(
                trade=synthetic_trade,
                remaining_quantity=stock_qty,
                original_quantity=stock_qty,
                price_per_unit=stock_cost_per_share,
            )
            baskets[underlying].append(stock_lot)

    if exercise_qty > 0:
        result.warnings.append(
            f"Exercise {trade.symbol} {trade.trade_date}: "
            f"niedobór {exercise_qty} kontraktów"
        )


def _process_assignment(
    trade: Trade,
    short_baskets: dict[str, deque[OpenLot]],
    baskets: dict[str, deque[OpenLot]],
    basket_key: str,
    nbp_client: NBPClient,
    result: FIFOResult,
    tax_year: int | None,
) -> None:
    """
    Przydzielenie opcji wystawionej (kod A, qty > 0 dla call writer).

    Writer call: musi sprzedać akcje po strike.
    Proceeds = (strike + premia) × ilość × mnożnik.
    Koszt pochodzi z FIFO koszyka akcji underlying.
    """
    short_basket = short_baskets[basket_key]
    assign_qty = abs(trade.quantity)

    if not short_basket:
        result.warnings.append(
            f"Assignment {trade.symbol} {trade.trade_date}: "
            f"brak otwartych krótkich pozycji opcyjnych"
        )
        return

    if trade.strike is None:
        result.warnings.append(
            f"Assignment {trade.symbol} {trade.trade_date}: "
            f"brak strike price"
        )
        return

    underlying = trade.underlying
    if not underlying:
        result.warnings.append(
            f"Assignment {trade.symbol} {trade.trade_date}: "
            f"brak underlying symbol"
        )
        return

    multiplier = Decimal(trade.multiplier)

    while assign_qty > 0 and short_basket:
        lot = short_basket[0]

        if lot.remaining_quantity <= assign_qty:
            matched_qty = lot.remaining_quantity
            assign_qty -= matched_qty
            premium_per_share = lot.price_per_unit

            # Syntetyczna sprzedaż akcji: proceeds = strike × qty × multiplier
            # Premia opcyjna jest już rozliczona w short basket
            stock_sell_qty = matched_qty * multiplier

            synthetic_sell = Trade(
                symbol=underlying,
                isin=trade.isin,
                asset_category=AssetCategory.STOCKS,
                currency=trade.currency,
                listing_exchange=trade.listing_exchange,
                trade_datetime=trade.trade_datetime,
                trade_date=trade.trade_date,
                settle_date=trade.settle_date,
                quantity=-stock_sell_qty,
                price=trade.strike,
                proceeds=stock_sell_qty * trade.strike,
                commission=Decimal("0"),
                multiplier=1,
                underlying=None,
            )

            # Rozlicz premię opcyjną jako osobny TaxLot (short close at 0)
            # Premia = zysk writera (sell_proceeds = premium, buy_cost = 0)
            _create_short_tax_lot(
                open_lot=lot,
                close_trade=trade,
                matched_qty=matched_qty,
                close_price=Decimal("0"),  # assignment = opcja "zużyta", nie kupiona
                nbp_client=nbp_client,
                result=result,
                tax_year=tax_year,
            )

            # Sprzedaż akcji przez FIFO koszyka stock
            _process_sell(
                synthetic_sell, baskets, underlying,
                nbp_client, result, tax_year,
            )

            short_basket.popleft()
        else:
            matched_qty = assign_qty
            lot.remaining_quantity -= matched_qty
            assign_qty = Decimal("0")

            stock_sell_qty = matched_qty * multiplier

            synthetic_sell = Trade(
                symbol=underlying,
                isin=trade.isin,
                asset_category=AssetCategory.STOCKS,
                currency=trade.currency,
                listing_exchange=trade.listing_exchange,
                trade_datetime=trade.trade_datetime,
                trade_date=trade.trade_date,
                settle_date=trade.settle_date,
                quantity=-stock_sell_qty,
                price=trade.strike,
                proceeds=stock_sell_qty * trade.strike,
                commission=Decimal("0"),
                multiplier=1,
                underlying=None,
            )

            _create_short_tax_lot(
                open_lot=lot,
                close_trade=trade,
                matched_qty=matched_qty,
                close_price=Decimal("0"),
                nbp_client=nbp_client,
                result=result,
                tax_year=tax_year,
            )

            _process_sell(
                synthetic_sell, baskets, underlying,
                nbp_client, result, tax_year,
            )

    if assign_qty > 0:
        result.warnings.append(
            f"Assignment {trade.symbol} {trade.trade_date}: "
            f"niedobór {assign_qty} kontraktów"
        )


# ────────────────────────────────────────────────────────────
# Short baskets (sell-to-open / buy-to-close)
# ────────────────────────────────────────────────────────────


def _process_short_open(
    trade: Trade,
    short_baskets: dict[str, deque[OpenLot]],
    basket_key: str,
) -> None:
    """
    Sell-to-open: wystawienie opcji (krótka pozycja).

    Tworzy lot w short_baskets z ceną = otrzymana premia.
    """
    lot = OpenLot(
        trade=trade,
        remaining_quantity=abs(trade.quantity),
        original_quantity=abs(trade.quantity),
        price_per_unit=trade.price,
    )
    short_baskets[basket_key].append(lot)


def _process_short_close(
    trade: Trade,
    short_baskets: dict[str, deque[OpenLot]],
    basket_key: str,
    nbp_client: NBPClient,
    result: FIFOResult,
    tax_year: int | None,
) -> None:
    """
    Buy-to-close lub wygaśnięcie krótkiej pozycji opcyjnej.

    Dopasowuje zamknięcie do lotów w short_baskets.
    TaxLot: sell_proceeds = premia z otwarcia, buy_cost = cena zamknięcia.
    """
    short_basket = short_baskets[basket_key]
    close_qty = abs(trade.quantity)

    if not short_basket:
        result.warnings.append(
            f"Short close {trade.symbol} {trade.trade_date}: "
            f"brak otwartych krótkich pozycji do dopasowania"
        )
        return

    while close_qty > 0 and short_basket:
        lot = short_basket[0]

        if lot.remaining_quantity <= close_qty:
            matched_qty = lot.remaining_quantity
            close_qty -= matched_qty

            _create_short_tax_lot(
                open_lot=lot,
                close_trade=trade,
                matched_qty=matched_qty,
                close_price=trade.price,
                nbp_client=nbp_client,
                result=result,
                tax_year=tax_year,
            )

            short_basket.popleft()
        else:
            matched_qty = close_qty
            lot.remaining_quantity -= matched_qty
            close_qty = Decimal("0")

            _create_short_tax_lot(
                open_lot=lot,
                close_trade=trade,
                matched_qty=matched_qty,
                close_price=trade.price,
                nbp_client=nbp_client,
                result=result,
                tax_year=tax_year,
            )

    if close_qty > 0:
        result.warnings.append(
            f"Short close {trade.symbol} {trade.trade_date}: "
            f"niedobór {close_qty} kontraktów"
        )


def _create_short_tax_lot(
    open_lot: OpenLot,
    close_trade: Trade,
    matched_qty: Decimal,
    close_price: Decimal,
    nbp_client: NBPClient,
    result: FIFOResult,
    tax_year: int | None,
) -> None:
    """
    Utwórz TaxLot dla zamknięcia krótkiej pozycji opcyjnej.

    Semantyka odwrócona:
    - sell_proceeds = premia z otwarcia (sell-to-open) = przychód
    - buy_cost = cena zamknięcia (buy-to-close) = koszt
    """
    open_trade = open_lot.trade
    multiplier = Decimal(open_trade.multiplier)

    # NBP rate dla otwarcia (sell-to-open = "przychód")
    open_nbp_date = compute_nbp_rate_date(open_trade.settle_date)
    open_nbp_rate = nbp_client.get_rate(open_trade.currency, open_nbp_date)

    # NBP rate dla zamknięcia (buy-to-close = "koszt")
    close_nbp_date = compute_nbp_rate_date(close_trade.settle_date)
    close_nbp_rate = nbp_client.get_rate(close_trade.currency, close_nbp_date)

    # Prowizje proporcjonalne
    open_commission = _proportional_commission(
        open_trade.commission, matched_qty, open_lot.original_quantity,
    )
    close_commission = _proportional_commission(
        close_trade.commission, matched_qty, abs(close_trade.quantity),
    )

    # Przychód = premia otrzymana × qty × multiplier
    sell_amount = open_lot.price_per_unit * matched_qty * multiplier
    sell_proceeds_pln = (sell_amount - abs(open_commission)) * open_nbp_rate

    # Koszt = cena zamknięcia × qty × multiplier
    buy_amount = close_price * matched_qty * multiplier
    buy_cost_pln = (buy_amount + abs(close_commission)) * close_nbp_rate

    profit_loss = sell_proceeds_pln - buy_cost_pln

    tax_lot = TaxLot(
        symbol=close_trade.symbol,
        isin=close_trade.isin,
        country=close_trade.country,
        listing_exchange=close_trade.listing_exchange,
        asset_category=close_trade.asset_category,
        currency=close_trade.currency,
        multiplier=close_trade.multiplier,
        # "Buy" = otwarcie krótkiej pozycji (sell-to-open) — mapujemy na daty kupna
        buy_trade_date=open_trade.trade_date,
        buy_settle_date=open_trade.settle_date,
        buy_nbp_rate_date=open_nbp_date,
        buy_nbp_rate=open_nbp_rate,
        buy_price=close_price,
        buy_quantity=matched_qty,
        buy_commission=close_commission,
        buy_cost_pln=buy_cost_pln,
        # "Sell" = zamknięcie (buy-to-close lub Ep) — mapujemy na daty sprzedaży
        sell_trade_date=close_trade.trade_date,
        sell_settle_date=close_trade.settle_date,
        sell_nbp_rate_date=close_nbp_date,
        sell_nbp_rate=close_nbp_rate,
        sell_price=open_lot.price_per_unit,
        sell_quantity=matched_qty,
        sell_commission=open_commission,
        sell_proceeds_pln=sell_proceeds_pln,
        profit_loss_pln=profit_loss,
    )

    if tax_year is None or tax_lot.tax_year == tax_year:
        result.tax_lots.append(tax_lot)


def _apply_corporate_action(
    action: CorporateAction,
    baskets: dict[str, deque[OpenLot]],
    result: FIFOResult,
) -> None:
    """Aplikuj corporate action (split) na otwarte loty."""
    if action.ratio_from is None or action.ratio_to is None:
        result.warnings.append(
            f"Corporate action {action.symbol} {action.action_date}: "
            f"brak ratio, pomijam"
        )
        return

    basket_key = action.symbol
    basket = baskets.get(basket_key)
    if not basket:
        return

    ratio_from = Decimal(str(action.ratio_from))
    ratio_to = Decimal(str(action.ratio_to))

    for lot in basket:
        # Ilość rośnie proporcjonalnie
        lot.remaining_quantity = lot.remaining_quantity * ratio_to / ratio_from
        lot.original_quantity = lot.original_quantity * ratio_to / ratio_from
        # Cena spada odwrotnie proporcjonalnie
        lot.price_per_unit = lot.price_per_unit * ratio_from / ratio_to
        # Łączny koszt nie zmienia się (quantity × price = const)
