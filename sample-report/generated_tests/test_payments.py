"""AI-suggested tests for payments.py. Review, wire fixtures, then run."""

def test_charge_invalid_amount():
    with pytest.raises(ValueError):
        charge(mock_gateway, -10)

def test_refund_propagates_error():
    mock_gateway.refund.side_effect = RuntimeError("gateway down")
    with pytest.raises(RuntimeError):
        refund(mock_gateway, "ch_123", 50)

def test_process_order_idempotent(mocker):
    gateway = mocker.Mock()
    cart = {"items": [{"price": 10, "qty": 2}], "currency": "USD"}
    token = "valid"
    # first call
    process_order(gateway, cart, token, idempotency_key="order-1")
    # second call with same key
    process_order(gateway, cart, token, idempotency_key="order-1")
    assert gateway.capture.call_count == 1

def test_process_order_unauthorized(mocker):
    gateway = mocker.Mock()
    cart = {"items": [], "owner": "alice"}
    token = "bob_token"
    with pytest.raises(AuthorizationError):
        process_order(gateway, cart, token)
