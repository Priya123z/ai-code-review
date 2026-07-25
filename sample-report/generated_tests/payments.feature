Feature: payments.py — AI-suggested coverage

  Scenario: Accurate payment calculation with decimal precision
    Given a cart with items totaling $100.00
    When the payment is processed with 2.9% + $0.30 fee
    Then the total charged should be exactly $103.20

  Scenario: Refund failure propagates error correctly
    Given a payment gateway that throws an exception on refund
    When a refund is attempted
    Then the exception should be propagated to the caller

  Scenario: Payment rejected for unauthorized cart access
    Given a cart owned by user A
    When user B attempts to process payment for that cart
    Then the payment should be rejected with authorization error
