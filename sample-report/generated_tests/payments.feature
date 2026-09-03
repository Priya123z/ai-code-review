Feature: payments.py — AI-suggested coverage

  Scenario: Reject invalid payment amounts
    Given a payment gateway mock
    And an amount of -10
    When charge(gateway, -10) is called
    Then a ValueError is raised

  Scenario: Refund failure is reported
    Given a payment gateway mock that raises RuntimeError on refund
    When refund(gateway, "ch_123", 50) is called
    Then the function raises RuntimeError

  Scenario: Idempotent order processing
    Given a payment gateway mock
    And a cart with items
    And a unique idempotency key
    When process_order(gateway, cart, token, idempotency_key) is called twice
    Then the gateway.capture method is called only once

  Scenario: Unauthorized cart access
    Given a payment gateway mock
    And a cart owned by user "alice"
    And a token representing user "bob"
    When process_order(gateway, cart, token) is called
    Then an AuthorizationError (or similar) is raised
