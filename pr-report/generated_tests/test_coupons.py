"""AI-suggested tests for examples/flask_shop/coupons.py. Review, wire fixtures, then run."""

def test_couponbook_independent_instances():
    cb1 = CouponBook()
    cb2 = CouponBook()
    cb1.add('SAVE10', 10)
    assert len(cb1.codes) == 1
    assert len(cb2.codes) == 0

def test_average_discount_empty():
    cb = CouponBook()
    assert cb.average_discount(100) == 0.0

def test_apply_best_coupon_empty_list():
    total = 200
    result = apply_best_coupon(total, [])
    assert result == total
