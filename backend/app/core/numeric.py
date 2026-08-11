"""Decimal arithmetic for money and quantities.

The `NUMERIC -> JavaScript number` mapping is the only lossy conversion in the
schema, so the rounding contract is implemented in one place rather than
re-derived at each call site (Data_Requirements_Database.md section 7.1).

The rule: both sides round identically at the boundary. The client rounds
before writing, the server rounds before storing, and all server-side
arithmetic uses `Decimal` rather than `float`. Because the stored values are
then bit-identical on device and server, last-write-wins never fires on a
value that merely *looks* different.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

QUANTITY_EXP = Decimal("0.001")   # 3 dp: 0.250 kg, 12.500 L, 1.750 bao
MONEY_EXP = Decimal("0.01")       # 2 dp, VND

ZERO_QUANTITY = Decimal("0.000")
ZERO_MONEY = Decimal("0.00")


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    """Coerce to Decimal without inheriting float's binary error.

    `Decimal(0.1)` is 0.1000000000000000055511151231257827021181583404541015625.
    `Decimal(str(0.1))` is exactly 0.1. Always go through the string.
    """
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Không phải số hợp lệ: {value!r}") from exc


def quantize_quantity(value: Decimal | int | float | str) -> Decimal:
    """Round to 3 decimal places, half-up. Mirrors the client's rounding."""
    return _to_decimal(value).quantize(QUANTITY_EXP, rounding=ROUND_HALF_UP)


def quantize_money(value: Decimal | int | float | str) -> Decimal:
    """Round to 2 decimal places, half-up. VND."""
    return _to_decimal(value).quantize(MONEY_EXP, rounding=ROUND_HALF_UP)


def line_total(quantity: Decimal, unit_cost: Decimal) -> Decimal:
    """quantity x unit_cost, rounded to money precision.

    Rounded once, at the end, rather than at each step -- rounding the
    intermediate product would drift by a đồng per line and by a visible
    amount across a season's worth of transactions.
    """
    return quantize_money(quantize_quantity(quantity) * quantize_money(unit_cost))
