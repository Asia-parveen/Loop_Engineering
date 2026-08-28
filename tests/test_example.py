import pytest
from src.example import add, greet


def test_add():
    assert add(2, 3) == 5
    assert add(0, 0) == 0
    assert add(-1, 1) == 0


def test_greet():
    assert greet("World") == "Hello, World!"
    assert greet("") == "Hello, !"