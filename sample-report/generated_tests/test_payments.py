"""AI-suggested tests for payments.py. Review, wire fixtures, then run."""

def test_payment_calculation_precision():
    # Test with Decimal values
    assert calculate_total(Decimal('100.00')) == Decimal('103.20')

def test_refund_failure_propagation():
    with pytest.raises(PaymentGatewayError):
        refund(failing_gateway, 'charge_id', 100.00)

def test_unauthorized_cart_payment_rejection():
    # Mock current_user to return different user than cart owner
    with pytest.raises(AuthorizationError):
        process_order(gateway, other_users_cart, user_b_token)
