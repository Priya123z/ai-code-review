Feature: examples/flask_shop/coupons.py, AI-suggested coverage

  Scenario: Separate CouponBook instances have independent code lists
    Given two CouponBook objects are created without passing a codes list
    When a coupon is added to the first CouponBook
    Then the second CouponBook's codes list remains empty

  Scenario: Average discount returns zero for empty coupon list
    Given a CouponBook with no coupons
    When average_discount is called with any total
    Then the result should be 0.0

  Scenario: apply_best_coupon with no coupons returns original total
    Given a total amount of 200
    And an empty list of coupons
    When apply_best_coupon is invoked
    Then the returned amount should equal the original total
