import unittest
from src.issue3 import format_title

class TestIssue3(unittest.TestCase):
    def test_format_title(self):
        # Should return "Hello World"
        self.assertEqual(format_title("hello world"), "Hello World")

if __name__ == "__main__":
    unittest.main()
