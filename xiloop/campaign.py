"""CampaignRunner - the heart of XiLoop.

Reads a test plan (scenarios + requirements), runs every scenario through
the LoopEngine, checks every requirement against the measured metrics, and
writes a pass/fail report. Think: pytest for control loops.

Test plan format (YAML, or the same structure as a dict):

    name: Actuator PID verification
    plant:  {type: actuator}                     # optional - see xiloop.build
    device: {type: pid, params: {kp: 2.0}}       # optional - see xiloop.build
    scenarios:
      - name: step_1rad
        setpoint: 1.0
        duration: 3.0
        dt: 0.001
    requirements:
      - id: REQ-1
        description: steady-state error below 2 %
        metric: steady_state_error
        max: 0.02
        scenarios: [step_1rad]                   # optional - default: all
"""
from dataclasses import dataclass, field

import yaml

from xiloop.engine import LoopEngine
from xiloop.interfaces import Device, Plant
from xiloop.metrics import METRICS, step_metrics


@dataclass
class RequirementResult:
    req_id: str
    description: str
    metric: str
    bound: str
    measured: float
    passed: bool


@dataclass
class CampaignResult:
    name: str
    scenario_results: dict = field(default_factory=dict)   # scenario -> [RequirementResult]
    runs: dict = field(default_factory=dict)               # scenario -> LoopResult
    metrics: dict = field(default_factory=dict)            # scenario -> metrics dict

    @property
    def passed(self) -> bool:
        return all(r.passed for results in self.scenario_results.values() for r in results)

    def summary(self) -> str:
        lines = [f"Campaign: {self.name} - {'PASS' if self.passed else 'FAIL'}"]
        for scen, results in self.scenario_results.items():
            for r in results:
                mark = "PASS" if r.passed else "FAIL"
                lines.append(f"  [{mark}] {scen} / {r.req_id}: {r.metric}="
                             f"{r.measured:.4g} (required {r.bound})")
        return "\n".join(lines)

    def markdown(self) -> str:
        rows = ["# XiLoop Test Report", "",
                f"**Campaign:** {self.name}  ",
                f"**Verdict:** {'PASS' if self.passed else 'FAIL'}", "",
                "| Scenario | Requirement | Description | Metric | Measured | Bound | Result |",
                "|---|---|---|---|---|---|---|"]
        for scen, results in self.scenario_results.items():
            for r in results:
                rows.append(f"| {scen} | {r.req_id} | {r.description} | {r.metric} | "
                            f"{r.measured:.4g} | {r.bound} | {'PASS' if r.passed else 'FAIL'} |")
        return "\n".join(rows) + "\n"

    def to_markdown(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.markdown())


def load_plan(plan) -> dict:
    """A path to a YAML file, YAML text, or an already-parsed dict -> dict."""
    if isinstance(plan, dict):
        return plan
    if "\n" not in plan and plan.endswith((".yaml", ".yml")):
        with open(plan, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return yaml.safe_load(plan) or {}


def check(req: dict, measured: float) -> tuple[bool, str]:
    passed, bounds = True, []
    if "max" in req:
        passed &= measured <= float(req["max"])
        bounds.append(f"<= {req['max']}")
    if "min" in req:
        passed &= measured >= float(req["min"])
        bounds.append(f">= {req['min']}")
    return passed, " and ".join(bounds)


class CampaignRunner:
    def __init__(self, device: Device, plant: Plant):
        self.engine = LoopEngine(device, plant)

    @classmethod
    def from_plan(cls, plan) -> "CampaignRunner":
        """Build device and plant from the plan's own `device:`/`plant:` sections."""
        from xiloop.build import build_device, build_plant
        plan = load_plan(plan)
        if "plant" not in plan:
            raise ValueError("test plan has no 'plant:' section")
        return cls(build_device(plan.get("device", {"type": "pid"})), build_plant(plan["plant"]))

    def run(self, plan, on_tick=None) -> CampaignResult:
        plan = load_plan(plan)
        result = CampaignResult(name=plan.get("name", "unnamed campaign"))
        requirements = plan.get("requirements") or []
        for req in requirements:
            if req.get("metric") not in METRICS:
                raise ValueError(f"requirement {req.get('id', '?')}: unknown metric "
                                 f"{req.get('metric')!r} - choose from {list(METRICS)}")

        for scen in plan.get("scenarios") or []:
            name = scen["name"]
            run = self.engine.run(setpoint=float(scen["setpoint"]),
                                  duration=float(scen["duration"]),
                                  dt=float(scen.get("dt", 0.001)),
                                  on_tick=on_tick)
            metrics = step_metrics(run)
            checks = []
            for req in requirements:
                if "scenarios" in req and name not in req["scenarios"]:
                    continue
                measured = metrics[req["metric"]]
                passed, bound = check(req, measured)
                checks.append(RequirementResult(
                    req_id=req.get("id", "REQ-?"), description=req.get("description", ""),
                    metric=req["metric"], bound=bound, measured=measured, passed=passed))
            result.scenario_results[name] = checks
            result.runs[name] = run
            result.metrics[name] = metrics
        return result
