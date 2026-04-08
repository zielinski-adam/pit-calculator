"""Kalkulator settlement date na bazie exchange_calendars."""
from __future__ import annotations

from datetime import date
from functools import lru_cache

import exchange_calendars as ec

from pit38.models.exchange import ExchangeConfig, get_exchange_config


@lru_cache(maxsize=16)
def _get_calendar(calendar_code: str) -> ec.ExchangeCalendar:
    """Cache kalendarzy giełdowych -- tworzenie jest kosztowne."""
    return ec.get_calendar(calendar_code)


def compute_settlement(trade_date: date, listing_exchange: str) -> date:
    """
    Oblicz settlement date dla transakcji.

    Algorytm:
    1. Pobierz konfigurację giełdy (calendar_code + cycle T+N)
    2. Pobierz cykl T+N dla daty transakcji (uwzględnia reformy T+1)
    3. Odlicz N dni roboczych giełdowych od trade_date

    Args:
        trade_date: Data zawarcia transakcji (z CSV)
        listing_exchange: Kod giełdy z IBKR (np. "NASDAQ", "NYSE", "AEB")

    Returns:
        Data rozrachunku (settlement date)
    """
    config = get_exchange_config(listing_exchange)
    return _compute_settlement_with_config(trade_date, config)


def _compute_settlement_with_config(trade_date: date, config: ExchangeConfig) -> date:
    """Oblicz settlement date mając konfigurację giełdy."""
    cycle = config.settlement_cycle(trade_date)
    calendar = _get_calendar(config.calendar_code)

    # Odlicz N dni sesyjnych (business days giełdowych) do przodu
    # settlement_date = trade_date + N business days
    current = trade_date
    days_counted = 0

    while days_counted < cycle:
        # Następny dzień kalendarzowy
        current = _next_calendar_day(current)
        # Liczymy tylko dni sesyjne
        if _is_session(calendar, current):
            days_counted += 1

    return current


def _next_calendar_day(d: date) -> date:
    """Następny dzień kalendarzowy."""
    from datetime import timedelta
    return d + timedelta(days=1)


def _is_session(calendar: ec.ExchangeCalendar, d: date) -> bool:
    """Sprawdź czy data jest dniem sesyjnym na danej giełdzie."""
    import pandas as pd
    ts = pd.Timestamp(d)
    # Sprawdź czy data jest w zakresie kalendarza
    if ts < calendar.first_session or ts > calendar.last_session:
        raise ValueError(
            f"Data {d} poza zakresem kalendarza "
            f"({calendar.first_session.date()} - {calendar.last_session.date()})"
        )
    return calendar.is_session(ts)


def compute_nbp_rate_date(settle_date: date) -> date:
    """
    Oblicz datę kursu NBP = ostatni dzień roboczy PRZED settlement date (D-1).

    NBP publikuje tabele A w każdy dzień roboczy (pon-pt, z wyjątkiem świąt).
    Dla uproszczenia zakładamy, że dni robocze NBP = pon-pt
    (NBP ma osobny kalendarz, ale świąt polskich jest mało w porównaniu z giełdowymi).
    """
    from datetime import timedelta
    current = settle_date - timedelta(days=1)
    # Cofaj się do ostatniego dnia roboczego (pon-pt)
    while current.weekday() >= 5:  # 5=sobota, 6=niedziela
        current -= timedelta(days=1)
    return current


def enrich_trades_with_settlement(
    trades: list,
) -> list:
    """
    Wzbogać listę Trade o settlement date.

    Zwraca NOWĄ listę z ustawionymi settle_date (Trade jest frozen,
    więc tworzymy kopie z model_copy).
    """
    enriched = []
    for trade in trades:
        settle = compute_settlement(trade.trade_date, trade.listing_exchange)
        enriched.append(trade.model_copy(update={"settle_date": settle}))
    return enriched
