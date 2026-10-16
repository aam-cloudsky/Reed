"""
Self-flow: a node that reads its own previous output.

`accumulate` produces `Total` and also consumes `Total`, marked `Sampled`:
it reads the value committed before the firing (a unit delay), so each
push() adds one deposit to the previous total. The self-input never
triggers the node; only a new `Deposit` does.
"""

from dataclasses import dataclass
from typing import Annotated

from reed import Flow, Sampled


@dataclass(frozen=True)
class Deposit:
    amount: float


@dataclass(frozen=True)
class Total:
    value: float


def accumulate(deposit: Deposit, previous: Annotated[Total, Sampled]) -> Total:
    return Total(previous.value + deposit.amount)


flow = Flow()
flow.add(accumulate)


if __name__ == "__main__":
    session = flow.session(observability="silent")
    session.feed(Total(0.0))  # initial state

    for amount in (10.0, 5.0, 2.5):
        session.feed(Deposit(amount))
        session.push()
        print("total:", session.snapshot()[Total].value)

    assert session.snapshot()[Total] == Total(17.5)
