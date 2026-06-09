import os

from hilo import PID, PIDDevice, ActuatorPlant, CampaignRunner

PLAN = os.path.join(os.path.dirname(__file__), "..", "examples", "actuator_pid", "testplan.yaml")


def test_good_gains_pass_campaign():
    result = CampaignRunner(PIDDevice(PID(kp=2.0, ki=1.0, kd=0.05)), ActuatorPlant()).run(PLAN)
    assert result.passed, result.summary()


def test_bad_gains_fail_campaign():
    # Aggressive gains, no damping -> huge overshoot -> REQ-2 must fail.
    result = CampaignRunner(PIDDevice(PID(kp=50.0, ki=0.0, kd=0.0)), ActuatorPlant()).run(PLAN)
    assert not result.passed


def test_report_is_written(tmp_path):
    result = CampaignRunner(PIDDevice(PID()), ActuatorPlant()).run(PLAN)
    out = tmp_path / "report.md"
    result.to_markdown(str(out))
    text = out.read_text(encoding="utf-8")
    assert "HiLo Test Report" in text and "REQ-1" in text
