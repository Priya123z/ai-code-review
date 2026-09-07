Feature: examples/flask_shop/coupons.py, AI-suggested coverage

  Scenario: Independent coupon books
    Given two CouponBook instances are created without passing codes
    When a coupon is added to the first instance
    Then the second instance's codes list remains empty

  Scenario: Average discount with no coupons
    Given a CouponBook with no coupons
    When average_discount is called with any total
    Then the result should be 0

  Scenario: Apply best coupon with empty list
    Given an empty list of coupons
    When apply_best_coupon is called with a total of 200
    Then the returned total should be 200

  Scenario: Add coupon with invalid percent
    Given a CouponBook instance
    When add is called with a percent of -5
    Then a ValueError should be raised
