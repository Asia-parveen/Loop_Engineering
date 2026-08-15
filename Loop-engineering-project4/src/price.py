"""Simple price calculator with a deliberate bug.

Final price = base price minus discount, then tax applied.
The BUG: tax is computed on the BASE price instead of the DISCOUNTED price.
"""


def final_price(base_price, discount_percent, tax_percent):
    """Return the final price after discount and tax.

    Correct rule: discount applies to the base price, then tax applies
    to the discounted (post-discount) price.
    """
    discount = base_price * discount_percent / 100
    discounted = base_price - discount
    tax = discounted * tax_percent / 100
    return discounted + tax
