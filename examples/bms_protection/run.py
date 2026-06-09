"""Advanced usage: a CUSTOM requirement checked with the LoopEngine directly.

Scenario: a battery protection device must open the contactor within 50 ms
of the current exceeding 50 A. This is not a step-response metric, so instead
of the CampaignRunner we use the LoopEngine as a library and write our own
check - the "pytest for control loops" style.

Run from the repo root:  python -m examples.bms_protection.run
"""
from dataclasses import dataclass

from xiloop import Device, Plant, LoopEngine

I_LIMIT = 50.0      # A - protection threshold
T_MAX = 0.050       # s - must shut down within 50 ms


@dataclass
class FaultyLoadPlant(Plant):
    """Battery feeding a load whose current ramps up (a developing fault).
    command = contactor state (1 closed / 0 open); measurement = current [A]."""
    ramp: float = 100.0   # A per second
    t: float = 0.0
    current: float = 0.0

    def reset(self) -> None:
        self.t = 0.0
        self.current = 0.0

    def step(self, command: float, dt: float) -> float:
        self.t += dt
        closed = command >= 0.5
        self.current = self.ramp * self.t if closed else 0.0
        return self.current


class ProtectionDevice(Device):
    """The logic under test: open the contactor when current exceeds the limit
    (latched - stays open). This is the 'firmware' we want to verify."""

    def __init__(self, limit: float = I_LIMIT):
        self.limit = limit
        self.tripped = False

    def reset(self) -> None:
        self.tripped = False

    def step(self, measurement: float, dt: float) -> float:
        if measurement > self.limit:
            self.tripped = True
        return 0.0 if self.tripped else 1.0


def main() -> None:
    run = LoopEngine(ProtectionDevice(), FaultyLoadPlant()).run(
        setpoint=0.0, duration=2.0, dt=0.001)

    # --- custom requirement check: shutdown within 50 ms of the violation ---
    t_violation = next(t for t, i in zip(run.t, run.measurement) if i > I_LIMIT)
    t_safe = next(t for t, i in zip(run.t, run.measurement)
                  if t > t_violation and i == 0.0)
    reaction = t_safe - t_violation

    verdict = "PASS" if reaction <= T_MAX else "FAIL"
    print(f"REQ-BMS-1: contactor opens within {T_MAX*1000:.0f} ms of overcurrent")
    print(f"  current exceeded {I_LIMIT:.0f} A at t={t_violation:.3f} s")
    print(f"  current reached 0 A        at t={t_safe:.3f} s")
    print(f"  reaction time = {reaction*1000:.1f} ms  ->  [{verdict}]")


if __name__ == "__main__":
    main()
