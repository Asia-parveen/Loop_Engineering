import unittest
from src.issue1 import calculate_discount

class TestIssue1(unittest.TestCase):
    def test_calculate_discount(self):
        # 200 - 10% should be 180.0
        self.assertEqual(calculate_discount(200.0, 10.0), 180.0)

if __name__ == "__main__":
    unittest.main()
