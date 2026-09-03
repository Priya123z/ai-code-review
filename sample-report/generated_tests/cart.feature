Feature: cart.py — AI-suggested coverage

  Scenario: Separate carts maintain independent item lists
    Given a new Cart instance cart_a
    And a new Cart instance cart_b
    When I add a product to cart_a
    Then cart_b.items should be empty

  Scenario: Adding a product with negative quantity raises error
    Given a new Cart instance
    When I attempt to add a product with qty -5
    Then a ValueError should be raised

  Scenario: Calling average_price on an empty cart returns 0
    Given a new empty Cart instance
    When I call average_price
    Then the result should be 0

  Scenario: Concurrent reservations do not oversell stock
    Given an inventory with product_id 1 having quantity 1
    When two threads simultaneously call reserve_stock for product_id 1 with qty 1
    Then only one call should return True and the other False
    And the final inventory quantity should be 0

  Scenario: Discount with None coupon returns original total and percent >100 is capped
    Given a total amount of 100
    When I call apply_discount with coupon set to None
    Then the result should be 100
    When I call apply_discount with a coupon of percent 150
    Then the result should be 0 (or raise a validation error depending on implementation)
