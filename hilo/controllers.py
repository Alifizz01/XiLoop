"""Built-in controllers. `PID` is the maths; `PIDDevice` adapts it to the
Device interface so the LoopEngine can run it. Users wrap their own logic the
same way."""
from dataclasses import dataclass

from hilo.interfaces import Device


@dataclass
class PID:
    kp: float = 2.0
    ki: float = 1.0
    kd: float = 0.05
    out_max: float = 10.0
    _integ: float = 0.0
    _prev_err: float = 0.0

    def reset(self) -> None:
        self._integ = 0.0
        self._prev_err = 0.0

    def update(self, setpoint: float, measurement: float, dt: float) -> float:
        err = setpoint - measurement
        self._integ += err * dt
        deriv = (err - self._prev_err) / dt if dt > 0 else 0.0
        self._prev_err = err
        out = self.kp * err + self.ki * self._integ + self.kd * deriv
        clamped = max(-self.out_max, min(self.out_max, out))
        if clamped != out:                 # anti-windup
            self._integ -= err * dt
        return clamped


class PIDDevice(Device):
    """Adapts a PID controller to HiLo's Device interface."""

    def __init__(self, pid: PID | None = None):
        self.pid = pid or PID()
        self._setpoint = 0.0

    def reset(self) -> None:
        self.pid.reset()

    def set_setpoint(self, setpoint: float) -> None:
        self._setpoint = setpoint

    def step(self, measurement: float, dt: float) -> float:
        return self.pid.update(self._setpoint, measurement, dt)
