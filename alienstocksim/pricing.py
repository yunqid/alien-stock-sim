"""
Last-traded prices are pushed from the WebSocket consumer so HTTP views can read them.
Keep TRADE_COMPANY in sync with the ticker used in static/alienstocksim/home.js.
"""

TRADE_COMPANY = "TESTTESTEST"


def _cache_key(company: str) -> str:
    return f"alienstocksim:last_price:{company}"


def set_last_price(company: str, price: float) -> None:
    from django.core.cache import cache

    cache.set(_cache_key(company), float(price), timeout=None)


def get_last_price(company: str, default: float = 100.0) -> float:
    from django.core.cache import cache

    v = cache.get(_cache_key(company))
    return float(v) if v is not None else default
