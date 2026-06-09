from xiloop import PID, PIDDevice, ActuatorPlant, LoopEngine


def test_loop_produces_expected_sample_count():
    run = LoopEngine(PIDDevice(PID()), ActuatorPlant()).run(setpoint=1.0, duration=1.0, dt=0.001)
    assert len(run.t) == 1000
    assert len(run.measurement) == 1000


def test_loop_is_deterministic():
    a = LoopEngine(PIDDevice(PID()), ActuatorPlant()).run(setpoint=1.0, duration=1.0)
    b = LoopEngine(PIDDevice(PID()), ActuatorPlant()).run(setpoint=1.0, duration=1.0)
    assert a.measurement == b.measurement


def test_controller_actually_tracks_setpoint():
    run = LoopEngine(PIDDevice(PID()), ActuatorPlant()).run(setpoint=1.0, duration=3.0)
    assert abs(run.measurement[-1] - 1.0) < 0.05
