"""User-plant example: verify a PID speed controller against a DC motor model.

Run from the repo root:  python -m examples.dc_motor.run
"""
import os

from hilo import PID, PIDDevice, CampaignRunner
from examples.dc_motor.plant import DCMotorPlant

HERE = os.path.dirname(__file__)


def main() -> None:
    device = PIDDevice(PID(kp=1.5, ki=3.0, kd=0.0, out_max=24.0))
    plant = DCMotorPlant()
    result = CampaignRunner(device, plant).run(os.path.join(HERE, "testplan.yaml"))
    print(result.summary())
    result.to_markdown(os.path.join(HERE, "report.md"))


if __name__ == "__main__":
    main()
