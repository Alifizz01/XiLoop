"""v1.0: devices over the line protocol, transfer-function plants, plans with
device/plant sections, CLI exit codes, and the REST API."""
import json
import os
import threading
import urllib.error
import urllib.request

import pytest

from xiloop import (PID, PIDDevice, ActuatorPlant, CampaignRunner, DeviceError, LoopEngine,
                    SocketDevice, TransferFunctionPlant, firmware, step_metrics)
from xiloop.build import build_device, build_plant
from xiloop.cli import main as cli

ROOT = os.path.join(os.path.dirname(__file__), "..")
PLAN = os.path.join(ROOT, "examples", "actuator_pid", "testplan.yaml")


@pytest.fixture(scope="module")
def board():
    srv = firmware.start(port=0)               # OS picks a free port
    yield srv.server_address[1]
    srv.shutdown()


def test_negative_step_measured_like_positive():
    run = lambda sp: step_metrics(LoopEngine(PIDDevice(PID()), ActuatorPlant()).run(sp, 3.0))
    pos, neg = run(1.0), run(-1.0)
    for k in ("overshoot_pct", "rise_time_s", "settling_time_s"):
        assert neg[k] == pytest.approx(pos[k])


@pytest.mark.parametrize("num,den,dc_gain", [("2", "0.5 1", 2.0), ("1", "1 0.4 4", 0.25), ("3", "2 1", 3.0)])
def test_transfer_function_reaches_dc_gain(num, den, dc_gain):
    p = TransferFunctionPlant(num=num, den=den)
    for _ in range(40000):
        y = p.step(1.0, 0.001)
    assert y == pytest.approx(dc_gain, rel=1e-2)


def test_transfer_function_rejects_improper():
    with pytest.raises(ValueError):
        TransferFunctionPlant(num="1 0 0", den="1 1")


def test_socket_firmware_matches_python_controller(board):
    py = CampaignRunner(PIDDevice(PID()), ActuatorPlant()).run(PLAN)
    dev = SocketDevice(port=board, params={"kp": 2.0, "ki": 1.0, "kd": 0.05})
    fw = CampaignRunner(dev, ActuatorPlant()).run(PLAN)
    dev.close()
    assert fw.passed
    for scen in py.metrics:
        assert fw.metrics[scen]["overshoot_pct"] == pytest.approx(py.metrics[scen]["overshoot_pct"], rel=1e-6)


def test_firmware_rejects_unknown_param(board):
    with pytest.raises(DeviceError, match="rejected"):
        SocketDevice(port=board, params={"bogus": 1}).reset()


def test_unreachable_firmware_is_a_clear_error():
    with pytest.raises(DeviceError, match="is it running"):
        SocketDevice(port=1, timeout=0.3)


def test_build_refuses_non_device_classes():
    with pytest.raises(ValueError, match="not a Device"):
        build_device({"type": "subprocess:run", "params": {"args": "x"}})
    assert isinstance(build_plant({"type": "actuator", "params": {"J": 0.02}}), ActuatorPlant)


def test_cli_exit_code_follows_verdict(tmp_path, capsys):
    assert cli(["run", PLAN, "--report", str(tmp_path / "r.md"), "--csv", str(tmp_path)]) == 0
    assert (tmp_path / "step_1rad.csv").exists()
    bad = tmp_path / "bad.yaml"
    bad.write_text(open(PLAN).read().replace("kp: 2.0", "kp: 50.0").replace("kd: 0.05", "kd: 0.0"))
    assert cli(["run", str(bad)]) == 1


def test_unknown_metric_is_reported():
    plan = {"plant": "actuator", "scenarios": [{"name": "s", "setpoint": 1, "duration": 1}],
            "requirements": [{"id": "R", "metric": "speed", "max": 1}]}
    with pytest.raises(ValueError, match="unknown metric"):
        CampaignRunner.from_plan(plan).run(plan)


# ---------------------------------------------------------------- REST API
@pytest.fixture(scope="module")
def api():
    from xiloop.server import make_server
    srv = make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(path, body=None, method=None, headers=None):
        h = {"Content-Type": "application/json"} if body is not None else {}
        h.update(headers or {})
        req = urllib.request.Request(base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None, headers=h)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)
    yield call
    srv.shutdown()


def test_api_simulate_and_campaign(api):
    code, r = api("/api/simulate", {"plant": {"type": "actuator"}, "device": {"type": "pid"}, "duration": 2})
    assert code == 200 and r["samples"] == 2000 and r["metrics"]["overshoot_pct"] > 0
    code, r = api("/api/campaign", {"plan": open(PLAN).read()})
    assert code == 200 and r["passed"] and "XiLoop Test Report" in r["markdown"]


def test_api_streams_a_job(api):
    _, j = api("/api/jobs", {"kind": "simulate", "duration": 0.5})
    for _ in range(200):
        _, s = api(f"/api/jobs/{j['id']}?since=0")
        if s["status"] != "running":
            break
    assert s["status"] == "done" and s["n"] == 500 and s["result"]["metrics"]


def test_api_rejects_cross_site_requests(api):
    assert api("/api/health", headers={"Host": "evil.example"})[0] == 403
    code, _ = api("/api/simulate", {}, headers={"Content-Type": "text/plain"})
    assert code == 415


def test_api_errors_are_readable(api):
    code, r = api("/api/simulate", {"plant": {"type": "nope"}})
    assert code == 400 and "unknown plant" in r["error"]


def test_custom_plant_resolves_from_working_folder(tmp_path, monkeypatch):
    # the installed `xiloop` / `xiloop-studio` commands don't put cwd on sys.path
    (tmp_path / "myheater.py").write_text(
        "from dataclasses import dataclass\nfrom xiloop import Plant\n"
        "@dataclass\nclass Heater(Plant):\n    k: float = 2.0\n"
        "    def step(self, u, dt): return u / self.k\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.path", [p for p in __import__("sys").path if p not in ("", str(tmp_path))])
    assert build_plant({"type": "myheater:Heater", "params": {"k": 4}}).step(8, 0.1) == 2
