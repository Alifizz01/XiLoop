"""XiLoop REST API - everything the Studio GUI can do, over plain HTTP + JSON.

    xiloop serve                       # http://127.0.0.1:8765  (API + Studio in a browser)

    GET    /api/health                 version check
    GET    /api/catalog                plants (+ parameters), device types, metrics, serial ports
    GET    /api/examples               bundled test plans
    POST   /api/plan/parse   {yaml}    -> {plan}
    POST   /api/plan/dump    {plan}    -> {yaml}
    POST   /api/simulate               one closed-loop run, waits for the result
    POST   /api/campaign               a whole test plan, waits for the verdict
    POST   /api/jobs                   same two, in the background: {"kind": "simulate"|"campaign", ...}
    GET    /api/jobs/<id>?since=N      live samples since index N, status, result when done
    DELETE /api/jobs/<id>              stop a running job
    GET|POST|DELETE /api/firmware      status / start {port} / stop the virtual board

simulate body:  {"plant": {...}, "device": {...}, "setpoint": 1, "duration": 3, "dt": 0.001,
                 "realtime": false}          (plant/device specs: see xiloop.build)
campaign body:  {"plan": <dict or YAML text>, "plant": {...}?, "device": {...}?}
                 plant/device in the body win over the plan's own sections.

Bound to 127.0.0.1 only. Requests must be JSON with a localhost Host header,
so web pages you visit cannot drive your bench.
"""
import glob
import json
import math
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import yaml

import xiloop
from xiloop import firmware
from xiloop.build import PLANTS, build_device, build_plant, plant_class, plant_params
from xiloop.campaign import CampaignRunner, load_plan
from xiloop.engine import LoopEngine
from xiloop.metrics import METRICS, step_metrics

STATIC = os.path.join(os.path.dirname(__file__), "studio")
EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")
MAX_POINTS = 4000
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
         ".svg": "image/svg+xml", ".png": "image/png"}


def _num(x):
    return None if isinstance(x, float) and not math.isfinite(x) else x


def _trace(run, start=0, max_points=MAX_POINTS):
    stride = max(1, math.ceil((len(run.t) - start) / max_points))
    sl = slice(start, None, stride)
    return {"t": run.t[sl], "y": run.measurement[sl], "u": run.command[sl], "setpoint": run.setpoint}


def _metrics(m):
    return {k: _num(v) for k, v in m.items()}


def catalog():
    plants = {}
    for name in PLANTS:
        try:
            cls = plant_class(name)
            plants[name] = {"params": plant_params(cls), "doc": (cls.__doc__ or "").strip()}
        except Exception as e:   # e.g. examples/ not importable when installed elsewhere
            plants[name] = {"params": {}, "doc": f"unavailable: {e}"}
    return {"version": xiloop.__version__, "plants": plants,
            "devices": {"pid": {"kp": 2.0, "ki": 1.0, "kd": 0.05, "out_max": 10.0},
                        "socket": {}, "serial": {}},
            "metrics": METRICS, "ports": ports()}


def ports():
    try:
        from serial.tools.list_ports import comports
        return [{"port": p.device, "desc": p.description} for p in comports()]
    except ImportError:
        return []


def examples():
    out = []
    for path in sorted(glob.glob(os.path.join(EXAMPLES, "*", "testplan.yaml"))):
        out.append({"name": os.path.basename(os.path.dirname(path)), "plan": load_plan(path)})
    return out


def _close(device):
    getattr(device, "close", lambda: None)()


class Job:
    """A simulation or campaign running in a background thread, with live telemetry."""

    def __init__(self, body):
        self.id = uuid.uuid4().hex[:8]
        self.kind = body.get("kind", "simulate")
        self.body = body
        self.status, self.error, self.result = "running", None, None
        self.scenario, self.seq, self.live = None, 0, None
        self._stop = False
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _tick(self, res):
        self.live = res
        return self._stop

    def _run(self):
        try:
            self.result = run_campaign(self.body, self) if self.kind == "campaign" \
                else simulate(self.body, self._tick)
            self.status = "stopped" if self._stop else "done"
        except Exception as e:
            self.status, self.error = "error", f"{type(e).__name__}: {e}"

    def snapshot(self, since: int):
        snap = {"id": self.id, "kind": self.kind, "status": self.status, "error": self.error,
                "scenario": self.scenario, "seq": self.seq}
        live = self.live
        if live is not None:
            n = len(live.t)
            snap["n"] = n
            snap["live"] = {"t": live.t[since:n], "y": live.measurement[since:n],
                            "u": live.command[since:n], "setpoint": live.setpoint}
        if self.status != "running":
            snap["result"] = self.result
        return snap


def simulate(body, on_tick=None):
    device = build_device(body.get("device", {"type": "pid"}))
    try:
        run = LoopEngine(device, build_plant(body.get("plant", "actuator"))).run(
            setpoint=float(body.get("setpoint", 1.0)), duration=float(body.get("duration", 3.0)),
            dt=float(body.get("dt", 0.001)), realtime=bool(body.get("realtime", False)),
            on_tick=on_tick)
    finally:
        _close(device)
    return {**_trace(run), "metrics": _metrics(step_metrics(run)), "samples": len(run.t)}


def run_campaign(body, job=None):
    plan = dict(load_plan(body.get("plan", {})))
    for key in ("plant", "device"):
        if body.get(key):
            plan[key] = body[key]
    runner = CampaignRunner.from_plan(plan)
    on_tick = None
    if job is not None:
        names = [s["name"] for s in plan.get("scenarios") or []]

        def on_tick(res, _names=iter(names)):
            if res is not job.live:          # a new scenario has started
                job.scenario, job.seq = next(_names, None), job.seq + 1
            return job._tick(res)
    try:
        result = runner.run(plan, on_tick=on_tick)
    finally:
        _close(runner.engine.device)
    scenarios = []
    for name, reqs in result.scenario_results.items():
        scenarios.append({"name": name, "metrics": _metrics(result.metrics[name]),
                          **_trace(result.runs[name]),
                          "requirements": [{**r.__dict__, "measured": _num(r.measured)} for r in reqs]})
    return {"name": result.name, "passed": result.passed, "markdown": result.markdown(),
            "scenarios": scenarios}


class _State:
    jobs: dict = {}
    board = None
    board_port = None


class Handler(BaseHTTPRequestHandler):
    server_version = f"XiLoop/{xiloop.__version__}"

    def log_message(self, *args):          # keep the console quiet
        pass

    def _send(self, code, payload=None, body=None, ctype="application/json"):
        if body is None:
            body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self):
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost")

    def _body(self):
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            raise PermissionError("requests must be sent as application/json")
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _dispatch(self, method):
        if not self._host_ok():
            return self._send(403, {"error": "XiLoop only answers on localhost"})
        url = urlparse(self.path)
        path = url.path.rstrip("/") or "/"
        try:
            if method == "GET" and not path.startswith("/api"):
                return self._static(path)
            body = self._body() if method == "POST" else {}
            out = self._route(method, path, body, parse_qs(url.query))
            if out is None:
                return self._send(404, {"error": f"no endpoint {method} {path}"})
            self._send(200, out)
        except PermissionError as e:
            self._send(415, {"error": str(e)})
        except Exception as e:
            self._send(400, {"error": f"{type(e).__name__}: {e}"})

    def _route(self, method, path, body, q):
        S = _State
        if path == "/api/health":
            return {"ok": True, "version": xiloop.__version__}
        if path == "/api/catalog":
            return catalog()
        if path == "/api/ports":
            return ports()
        if path == "/api/examples":
            return examples()
        if path == "/api/plan/parse" and method == "POST":
            return {"plan": yaml.safe_load(body.get("yaml", "")) or {}}
        if path == "/api/plan/dump" and method == "POST":
            return {"yaml": yaml.safe_dump(body.get("plan", {}), sort_keys=False)}
        if path == "/api/simulate" and method == "POST":
            return simulate(body)
        if path == "/api/campaign" and method == "POST":
            return run_campaign(body)
        if path == "/api/jobs" and method == "POST":
            job = Job(body)
            S.jobs[job.id] = job
            for old in list(S.jobs)[:-20]:          # keep the last 20
                S.jobs.pop(old)
            job.thread.start()
            return {"id": job.id}
        if path.startswith("/api/jobs/"):
            job = S.jobs.get(path.rsplit("/", 1)[1])
            if job is None:
                raise KeyError("unknown job id")
            if method == "DELETE":
                job._stop = True
                return {"id": job.id, "stopping": True}
            return job.snapshot(int(q.get("since", ["0"])[0]))
        if path == "/api/firmware":
            if method == "POST" and S.board is None:
                S.board_port = int(body.get("port", 5555))
                S.board = firmware.start(S.board_port)
            elif method == "DELETE" and S.board is not None:
                S.board.shutdown()
                S.board.server_close()
                S.board = None
            return {"running": S.board is not None, "port": S.board_port}
        return None

    def _static(self, path):
        rel = "index.html" if path == "/" else path.lstrip("/")
        full = os.path.normpath(os.path.join(STATIC, rel))
        if not full.startswith(STATIC) or not os.path.isfile(full):
            return self._send(404, {"error": "not found"})
        with open(full, "rb") as f:
            self._send(200, body=f.read(), ctype=TYPES.get(os.path.splitext(full)[1], "application/octet-stream"))

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_DELETE(self):
        self._dispatch("DELETE")


def make_server(port: int = 8765) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    return srv


def serve(port: int = 8765) -> None:
    srv = make_server(port)
    print(f"XiLoop API + Studio on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
