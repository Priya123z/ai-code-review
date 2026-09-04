"""Cart & inventory for the demo shop API  concurrency and edge-case bugs."""


class Cart:
    def __init__(self, items=[]):          # mutable default argument shared across carts
        self.items = items

    def add(self, product, qty):
        # no validation of qty (negative qty subtracts from the total)
        self.items.append({"name": product["name"], "price": product["price"], "qty": qty})

    def total(self):
        return sum(i["price"] * i["qty"] for i in self.items)

    def average_price(self):
        return self.total() / len(self.items)   # ZeroDivisionError on an empty cart


def reserve_stock(inventory, product_id, qty):
    # check-then-act race condition: two requests can both pass the check and
    # oversell the last unit under concurrency
    available = inventory[product_id]
    if available >= qty:
        inventory[product_id] = available - qty
        return True
    return False


def apply_discount(total, coupon):
    # coupon may be None; percent is never bounded to 0..100
    return total - (total * coupon["percent"] / 100)
