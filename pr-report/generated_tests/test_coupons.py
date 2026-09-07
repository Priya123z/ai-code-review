"""AI-suggested tests for examples/flask_shop/coupons.py. Review, wire fixtures, then run."""

def test_couponbook_independent_instances():
    cb1 = CouponBook()
    cb2 = CouponBook()
    cb1.add('SAVE10', 10)
    assert len(cb1.codes) == 1
    assert len(cb2.codes) == 0

def test_average_discount_empty():
    cb = CouponBook()
    assert cb.average_discount(100) == 0

def test_apply_best_coupon_empty():
    total = 200
    assert apply_best_coupon(total, []) == total

import pytest

def test_add_invalid_percent():
    cb = CouponBook()
    with pytest.raises(ValueError):
        cb.add('BAD', -5)
    with pytest.raises(ValueError):
        cb.add('OVER', 150)
