import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from calculator import subtract


class TestSubtract(unittest.TestCase):
    def test_subtract_positive(self):
        self.assertEqual(subtract(5, 3), 2)

    def test_subtract_negative(self):
        self.assertEqual(subtract(0, 5), -5)

    def test_subtract_zero(self):
        self.assertEqual(subtract(3, 0), 3)


if __name__ == "__main__":
    unittest.main()
