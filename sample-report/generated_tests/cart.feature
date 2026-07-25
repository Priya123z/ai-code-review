Feature: cart.py — AI-suggested coverage

  Scenario: Independent cart instances
    Given two Cart instances created with default arguments
    When I add an item to the first cart
    Then the second cart should remain empty

  Scenario: Concurrent inventory check
    Given an inventory with 1 unit of a product
    When two threads simultaneously reserve 1 unit each
    Then only one reservation should succeed

  Scenario: Empty cart average price
    Given an empty cart
    When I call average_price()
    Then it should return 0 or handle gracefully without error
