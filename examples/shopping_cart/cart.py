"""A deliberately imperfect shopping-cart module — the demo target for `aiqa scan`.

It contains a spread of realistic defects (a division-by-zero, a mutable
default argument, a missing None-check, a float-money bug, no input validation)
so the AI report has something concrete to find.
"""


class ShoppingCart:
    def __init__(self, items=[]):          # mutable default argument
        self.items = items

    def add_item(self, name, price, qty):
        # no validation: negative price/qty, empty name all pass silently
        self.items.append({"name": name, "price": price, "qty": qty})

    def total(self):
        total = 0.0
        for item in self.items:
            total += item["price"] * item["qty"]   # float money → rounding drift
        return total

    def average_item_price(self):
        return self.total() / len(self.items)       # ZeroDivisionError on empty cart

    def apply_coupon(self, coupon):
        # coupon may be None; percent may exceed 100
        return self.total() - (self.total() * coupon["percent"] / 100)

    def find_item(self, name):
        for item in self.items:
            if item["name"] == name:
                return item
        # falls through returning None; callers index into it


def checkout(cart, user):
    print("Charging card for " + user.name)       # AttributeError if user is None
    return cart.total()
