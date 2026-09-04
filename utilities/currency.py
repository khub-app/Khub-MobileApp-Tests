import re
from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")


def parse_currency(text: str) -> float:
    """Extract a dollar amount from label text like "$19.80" or "Total $19.80"
    into a float. Mirrors khub-pos-tests' utilities/currency.py — never
    hardcode expected amounts, always parse the live value."""
    match = re.search(r"[\d,]+\.?\d*", text)
    if not match:
        raise ValueError(f"No numeric amount found in {text!r}")
    return float(match.group().replace(",", ""))


def money(value) -> Decimal:
    """Coerce a float/str/Decimal UI amount to a 2dp Decimal for
    currency-safe comparison and arithmetic. Going through str() first
    avoids binary-float artifacts beyond the 2 decimals the UI already
    shows."""
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


def line_subtotal(price, qty) -> Decimal:
    """price x qty, rounded to cents — the expected per-line subtotal."""
    return money(Decimal(str(price)) * Decimal(str(qty)))
