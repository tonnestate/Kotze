import unittest

from app.pricing import total_cents


class PublicPricingTests(unittest.TestCase):
    """Deliberately minimal public suite (the hidden host oracle is broader)."""

    def test_small_order_has_no_discount(self):
        self.assertEqual(total_cents(2, 100), 200)

    def test_ten_units_get_the_discount(self):
        self.assertEqual(total_cents(10, 100), 900)
