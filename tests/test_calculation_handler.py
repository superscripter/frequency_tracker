import pytest
import os
from calculation_handler import CalculationHandler

@pytest.fixture(scope="module")
def calculation_handler():
    handler = CalculationHandler()
    yield handler

def test_hash_password(calculation_handler):
    password = "password"
    hashed_password = calculation_handler.hash_password(password)
    assert hashed_password is not None
    assert hashed_password != password
    assert calculation_handler.verify_password(password, hashed_password)

def test_hash_password_invalid(calculation_handler):
    password = "password"
    hashed_password = calculation_handler.hash_password(password)
    assert hashed_password is not None