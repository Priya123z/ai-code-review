Feature: examples/flask_shop/coupons.py, AI-suggested coverage

  Scenario: Separate CouponBook objects have independent code collections
    Given a new CouponBook instance cb1
    And a new CouponBook instance cb2
    When I add a coupon "SAVE10" with 10% to cb1
    Then cb2.codes should be empty

  Scenario: average_discount handles empty coupon list without error
    Given a CouponBook with no coupons
    When I call average_discount with a total of 100
    Then the result should be 0

  Scenario: apply_best_coupon with empty coupon list
    Given a total amount of 200
    And an empty list of coupons
    When I apply_best_coupon
    Then the returned total should equal the original amount

  Scenario: add method validates percent bounds
    Given a CouponBook
    When I try to add a coupon with percent -5
    Then a ValueError should be raised
