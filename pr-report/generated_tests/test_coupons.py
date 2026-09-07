"""AI-suggested tests for examples/flask_shop/coupons.py. Review, wire fixtures, then run."""

def test_couponbook_default_list_is_not_shared():
    cb1 = CouponBook()
    cb2 = CouponBook()
    cb1.add('SAVE10', 10)
    assert cb2.codes == []

def test_average_discount_empty_book_returns_zero():
    cb = CouponBook()
    assert cb.average_discount(100) == 0

def test_apply_best_coupon_empty_list_returns_original_total():
    total = 200
    assert apply_best_coupon(total, []) == total

def test_add_invalid_percent_raises():
    cb = CouponBook()
    with pytest.raises(ValueError):
        cb.add('BAD', -5)
