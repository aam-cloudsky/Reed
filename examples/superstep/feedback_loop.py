"""
Feedback loop: a controller and its plant.

`controller` reads the measurement and produces a command; `plant` reads the
command and produces the next measurement, which feeds `controller` again.
Each node runs at most once per push(), so the loop advances one step per
push(): the measurement fed back takes effect in the next push(), as a unit
delay (u[k] = Kp * (r - y[k-1])).
"""

from dataclasses import dataclass

from reed import Flow


@dataclass(frozen=True)
class Tick:
    k: int


@dataclass(frozen=True)
class Measurement:
    value: float


@dataclass(frozen=True)
class Command:
    value: float


SETPOINT = 10.0


def controller(tick: Tick, measurement: Measurement) -> Command:
    return Command(0.5 * (SETPOINT - measurement.value))


def plant(command: Command) -> Measurement:
    return Measurement(SETPOINT - command.value)


flow = Flow()
flow.add(controller)
flow.add(plant)


if __name__ == "__main__":
    session = flow.session(observability="silent")
    session.feed(Measurement(0.0))

    for k in range(1, 6):
        session.feed(Tick(k))
        session.push()
        print(f"k={k}  y={session.snapshot()[Measurement]}")

    assert session.snapshot()[Measurement] == Measurement(9.6875)
