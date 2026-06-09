"""LoopEngine - the heartbeat of XiLoop.

Runs the device<->plant exchange at a fixed step. Two timing modes:
  * fast (default): as fast as the CPU allows - ideal for CI and batch testing.
  * realtime: each tick is synchronized to the wall clock - feels like a bench.
"""
import time
from dataclasses import dataclass, field

from xiloop.interfaces import Device, Plant


@dataclass
class LoopResult:
    """Telemetry of one scenario run."""
    t: list[float] = field(default_factory=list)
    measurement: list[float] = field(default_factory=list)
    command: list[float] = field(default_factory=list)
    setpoint: float = 0.0
    dt: float = 0.001

    def to_csv(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write("t,setpoint,measurement,command\n")
            for i in range(len(self.t)):
                f.write(f"{self.t[i]:.6f},{self.setpoint},"
                        f"{self.measurement[i]:.6f},{self.command[i]:.6f}\n")


class LoopEngine:
    """Wires a Device to a Plant and runs the closed loop."""

    def __init__(self, device: Device, plant: Plant):
        self.device = device
        self.plant = plant

    def run(self, setpoint: float, duration: float, dt: float = 0.001,
            realtime: bool = False) -> LoopResult:
        self.device.reset()
        self.plant.reset()
        self.device.set_setpoint(setpoint)

        res = LoopResult(setpoint=setpoint, dt=dt)
        meas = 0.0
        n = int(duration / dt)
        t0 = time.perf_counter()
        for i in range(n):
            cmd = self.device.step(meas, dt)
            meas = self.plant.step(cmd, dt)
            res.t.append(i * dt)
            res.measurement.append(meas)
            res.command.append(cmd)
            if realtime:
                target = t0 + (i + 1) * dt
                while time.perf_counter() < target:
                    pass
        return res
