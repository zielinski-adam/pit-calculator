"""
Silnik FIFO multi-year z settlement date ordering.

Klucz sortowania: (settle_date, trade_date)
Osobny koszyk per instrument (symbol + asset_category).
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pit38.models.corporate_action import CorporateAction
from pit38.models.enums import AssetCategory
from pit38.models.tax_lot import TaxLot
from pit38.models.trade import Trade
from pit38.nbp.client import NBPClient
from pit38.settlement.calculator import compute_nbp_rate_date


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

        if trade.is_buy:
            _process_buy(trade, baskets, basket_key)
        elif trade.is_sell:
            _process_sell(trade, baskets, basket_key, nbp_client, result, tax_year)

    # Aplikuj pozostałe corporate actions
    while action_idx < len(sorted_actions):
        _apply_corporate_action(sorted_actions[action_idx], baskets, result)
        action_idx += 1

    # Zapisz otwarte pozycje
    for key, basket in baskets.items():
        if basket:
            result.open_positions[key] = list(basket)

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
    # Koszt kupna: (cena × ilość + |prowizja|) × kurs NBP
    # Prowizja jest ujemna, więc bierzemy wartość bezwzględną
    buy_amount = buy_lot.price_per_unit * matched_qty
    buy_cost_pln = (buy_amount + abs(buy_commission)) * buy_nbp_rate

    # Przychód sprzedaży: (cena × ilość - |prowizja|) × kurs NBP
    sell_amount = sell_trade.price * matched_qty
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
