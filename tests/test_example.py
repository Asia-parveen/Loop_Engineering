import pytest
from src.example import add, greet


def test_add():
    # Correct behavior: add(2, 3) should equal 5
    # The buggy code returns a + b + 1 = 6 (off-by-one)
    assert add(2, 3) == 5, f"Expected 5 but got {add(2, 3)} (off-by-one error)"
    assert add(0, 0) == 0, f"Expected 0 but got {add(0, 0)}"
    assert add(-1, 1) == 0, f"Expected 0 but got {add(-1, 1)}"


def test_greet():
    assert greet("World") == "Hello, World!"
    assert greet("") == "Hello, !"