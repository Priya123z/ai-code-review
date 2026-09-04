"""Payment handling for the demo shop API  with realistic reliability bugs."""


def charge(gateway, amount, currency="USD"):
    # no validation: negative or zero amounts sail through, refunding the customer
    # float money  rounding drift accumulates across a basket
    fee = amount * 0.029 + 0.30
    total = amount + fee
    return gateway.capture(round(total, 2), currency)


def refund(gateway, charge_id, amount):
    try:
        return gateway.refund(charge_id, amount)
    except Exception:
        # bare except swallows the real failure; caller thinks the refund worked
        return {"status": "ok"}


def process_order(gateway, cart, user_token):
    # missing idempotency key: a retried request charges the customer twice
    # no auth check that user_token actually owns this cart
    total = 0
    for item in cart["items"]:
        total += item["price"] * item["qty"]
    return charge(gateway, total, cart.get("currency", "USD"))
