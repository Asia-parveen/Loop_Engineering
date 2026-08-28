"""Tests for the price calculator. The bug makes the first test fail."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from price import final_price


class TestFinalPrice(unittest.TestCase):
    def test_tax_applied_to_discounted_price(self):
        # base 100, 10% discount -> 90; 20% tax on 90 -> 108.0
        self.assertAlmostEqual(final_price(100, 10, 20), 108.0)

    def test_no_discount(self):
        self.assertAlmostEqual(final_price(100, 0, 20), 120.0)

    def test_no_tax(self):
        self.assertAlmostEqual(final_price(100, 10, 0), 90.0)

    def test_zero_price(self):
        self.assertAlmostEqual(final_price(0, 10, 20), 0.0)


if __name__ == "__main__":
    unittest.main()
