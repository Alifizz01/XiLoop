"""The two plug-in points of XiLoop.

Anything that implements `Device` can be tested; anything that implements
`Plant` can be controlled. The LoopEngine only ever talks to these two
interfaces - which is what lets the same test campaign run against a Python
prototype today and emulated/real firmware later.
"""
from abc import ABC, abstractmethod


class Device(ABC):
    """The thing being tested (controller / firmware / ECU).

    Each loop tick the engine gives it the latest plant measurement and it
    returns a command (actuator effort).
    """

    def reset(self) -> None:
        """Return to initial state before a scenario starts."""

    def set_setpoint(self, setpoint: float) -> None:
        """Target value the device should drive the plant to."""

    @abstractmethod
    def step(self, measurement: float, dt: float) -> float:
        """One control tick: measurement in, command out."""


class Plant(ABC):
    """The simulated system under control (actuator, motor, battery, ...)."""

    def reset(self) -> None:
        """Return to initial state before a scenario starts."""

    @abstractmethod
    def step(self, command: float, dt: float) -> float:
        """Advance the physics by dt under `command`; return new measurement."""
