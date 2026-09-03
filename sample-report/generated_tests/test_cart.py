"""AI-suggested tests for cart.py. Review, wire fixtures, then run."""

def test_carts_are_independent():
    cart_a = Cart()
    cart_b = Cart()
    cart_a.add({"name": "Widget", "price": 10}, 1)
    assert cart_b.items == []

import pytest

def test_add_negative_quantity_raises():
    cart = Cart()
    with pytest.raises(ValueError):
        cart.add({"name": "Gadget", "price": 20}, -5)

def test_average_price_empty_cart_returns_zero():
    cart = Cart()
    assert cart.average_price() == 0

import threading

def test_reserve_stock_thread_safety():
    inventory = {1: 1}
    results = []
    def worker():
        results.append(reserve_stock(inventory, 1, 1))
    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start(); t2.start(); t1.join(); t2.join()
    assert results.count(True) == 1
    assert results.count(False) == 1
    assert inventory[1] == 0

def test_apply_discount_edge_cases():
    assert apply_discount(100, None) == 100
    # assuming implementation caps at 100%
    assert apply_discount(100, {"percent": 150}) == 0
