import matplotlib
matplotlib.use("Agg")  # headless - no display needed

from xiloop import PID, PIDDevice, ActuatorPlant, LoopEngine, step_metrics
from xiloop.dashboard import TuningDashboard


def _run(pid):
    return LoopEngine(PIDDevice(pid), ActuatorPlant()).run(setpoint=1.0, duration=3.0)


def test_settling_time_of_good_controller_is_finite_and_small():
    m = step_metrics(_run(PID(kp=2.0, ki=1.0, kd=0.05)))
    assert m["settling_time_s"] < 1.5


def test_settling_time_is_inf_when_response_never_settles():
    # weak proportional-only controller -> large steady-state offset
    m = step_metrics(_run(PID(kp=0.05, ki=0.0, kd=0.0)))
    assert m["settling_time_s"] == float("inf")


def _make_dashboard():
    return TuningDashboard(
        make_device=lambda kp, ki, kd: PIDDevice(PID(kp=kp, ki=ki, kd=kd)),
        make_plant=ActuatorPlant,
        params={"kp": (0.1, 10.0, 2.0), "ki": (0.0, 5.0, 1.0), "kd": (0.0, 0.5, 0.05)},
        setpoint=1.0, duration=3.0)


def test_dashboard_compute_returns_run_and_metrics():
    dash = _make_dashboard()
    run, m = dash.compute(**dash.initial_values())
    assert len(run.t) == 3000
    assert "settling_time_s" in m and "overshoot_pct" in m


def test_dashboard_builds_figure_headless():
    fig = _make_dashboard().build_figure()
    assert fig is not None
    assert len(fig.axes) >= 5  # main plot + 3 param sliders + setpoint slider
