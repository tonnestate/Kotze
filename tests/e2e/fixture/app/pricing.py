"""Order pricing rules (integer cents only, no floating point)."""

DISCOUNT_THRESHOLD = 10  # units


def total_cents(quantity: int, unit_price_cents: int) -> int:
    """Return the order total in cents.

    Business rule: orders of DISCOUNT_THRESHOLD or more units receive a 10 %
    discount on the gross total, rounded half up to whole cents.
    """
    if quantity < 0 or unit_price_cents < 0:
        raise ValueError('quantity and unit price must be non-negative')
    gross = quantity * unit_price_cents
    if quantity > DISCOUNT_THRESHOLD:
        return (gross * 9 + 5) // 10
    return gross
