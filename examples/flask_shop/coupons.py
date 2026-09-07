"""Discount codes for the demo shop API.

Stacked coupon codes applied to a cart total, plus the average discount per
code so the checkout page can show "you saved X per code".
"""


class CouponBook:
    def __init__(self, codes=[]):
        self.codes = codes

    def add(self, code, percent):
        self.codes.append({"code": code, "percent": percent})

    def discount_for(self, total):
        return sum(total * (c["percent"] / 100) for c in self.codes)

    def average_discount(self, total):
        return self.discount_for(total) / len(self.codes)


def apply_best_coupon(total, codes):
    best = max(codes, key=lambda c: c["percent"])
    return total - total * (best["percent"] / 100)
