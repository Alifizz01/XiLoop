"""HiLo example: verify a PID position controller against an actuator model.

Run from the repo root:
    python -m examples.actuator_pid.run
"""
import os

from hilo import PID, PIDDevice, ActuatorPlant, CampaignRunner, LoopEngine

HERE = os.path.dirname(__file__)


def main() -> None:
    device = PIDDevice(PID(kp=2.0, ki=1.0, kd=0.05))
    plant = ActuatorPlant()

    # 1) Run the full requirement campaign defined in testplan.yaml
    runner = CampaignRunner(device, plant)
    result = runner.run(os.path.join(HERE, "testplan.yaml"))
    print(result.summary())
    result.to_markdown(os.path.join(HERE, "report.md"))
    print("Report written to examples/actuator_pid/report.md")

    # 2) Record one run's telemetry + plot (optional)
    run = LoopEngine(device, plant).run(setpoint=1.0, duration=3.0)
    run.to_csv(os.path.join(HERE, "telemetry.csv"))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(7, 3.2))
        ax.axhline(run.setpoint, ls="--", c="k", lw=1, label="setpoint")
        ax.plot(run.t, run.measurement, c="#0b5fa5", label="position")
        ax.set_xlabel("time [s]"); ax.set_ylabel("position [rad]")
        ax.legend(); fig.tight_layout()
        fig.savefig(os.path.join(HERE, "step_response.png"), dpi=130)
        print("Plot written to examples/actuator_pid/step_response.png")
    except Exception as e:
        print("Plot skipped:", e)


if __name__ == "__main__":
    main()
