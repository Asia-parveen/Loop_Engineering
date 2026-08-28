import unittest
from src.issue2 import get_first_n_elements

class TestIssue2(unittest.TestCase):
    def test_get_first_n_elements(self):
        # Should return first 2 elements: [1, 2]
        self.assertEqual(get_first_n_elements([1, 2, 3], 2), [1, 2])

if __name__ == "__main__":
    unittest.main()
