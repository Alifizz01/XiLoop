"""Interactive PID tuning for the actuator demo (XiLoop v0.2 dashboard).

Run from the repo root:  python -m examples.actuator_pid.tune
Drag the sliders - the loop re-runs instantly and the metrics update.
When you like the response, copy the gains into run.py / your campaign.
"""
from xiloop import PID, PIDDevice, ActuatorPlant
from xiloop.dashboard import TuningDashboard


def main() -> None:
    TuningDashboard(
        make_device=lambda kp, ki, kd: PIDDevice(PID(kp=kp, ki=ki, kd=kd)),
        make_plant=ActuatorPlant,
        params={"kp": (0.1, 10.0, 2.0),
                "ki": (0.0, 5.0, 1.0),
                "kd": (0.0, 0.5, 0.05)},
        setpoint=1.0,
        duration=3.0,
    ).show()


if __name__ == "__main__":
    main()
