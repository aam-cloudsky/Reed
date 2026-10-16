"""
Diamond: one change, two branches, one join.

`price` feeds both `tax` and `discount`; `quote` joins them. In a superstep
execution, `tax` and `discount` run first, together; `quote` runs once, after
both, and always sees two values derived from the same price.
"""

from dataclasses import dataclass

from reed import Flow


@dataclass(frozen=True)
class Price:
    value: float


@dataclass(frozen=True)
class Taxed:
    value: float


@dataclass(frozen=True)
class Discounted:
    value: float


@dataclass(frozen=True)
class Quote:
    taxed: float
    discounted: float


def tax(price: Price) -> Taxed:
    return Taxed(price.value * 1.1)


def discount(price: Price) -> Discounted:
    return Discounted(price.value * 0.9)


def quote(taxed: Taxed, discounted: Discounted) -> Quote:
    print(f"quote: taxed={taxed.value:.1f} discounted={discounted.value:.1f}")
    return Quote(taxed.value, discounted.value)


flow = Flow()
flow.add(tax)
flow.add(discount)
flow.add(quote)


if __name__ == "__main__":
    session = flow.session(observability="silent")
    for price in (100.0, 200.0):
        session.feed(Price(price))
        session.push()

    assert session.snapshot()[Quote] == Quote(200.0 * 1.1, 200.0 * 0.9)
