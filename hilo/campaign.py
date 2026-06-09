"""CampaignRunner — the heart of HiLo.

Reads a YAML test plan (scenarios + requirements), runs every scenario through
the LoopEngine, checks every requirement against the measured metrics, and
writes a pass/fail report. Think: pytest for control loops.

Test plan format (YAML):

    name: Actuator PID verification
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
"""
from dataclasses import dataclass, field

import yaml

from hilo.engine import LoopEngine
from hilo.interfaces import Device, Plant
from hilo.metrics import step_metrics


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

    @property
    def passed(self) -> bool:
        return all(r.passed for results in self.scenario_results.values() for r in results)

    def summary(self) -> str:
        lines = [f"Campaign: {self.name} — {'PASS' if self.passed else 'FAIL'}"]
        for scen, results in self.scenario_results.items():
            for r in results:
                mark = "PASS" if r.passed else "FAIL"
                lines.append(f"  [{mark}] {scen} / {r.req_id}: {r.metric}="
                             f"{r.measured:.4g} (required {r.bound})")
        return "\n".join(lines)

    def to_markdown(self, path: str) -> None:
        rows = ["# HiLo Test Report", "",
                f"**Campaign:** {self.name}  ",
                f"**Verdict:** {'✅ PASS' if self.passed else '❌ FAIL'}", "",
                "| Scenario | Requirement | Description | Metric | Measured | Bound | Result |",
                "|---|---|---|---|---|---|---|"]
        for scen, results in self.scenario_results.items():
            for r in results:
                rows.append(f"| {scen} | {r.req_id} | {r.description} | {r.metric} | "
                            f"{r.measured:.4g} | {r.bound} | {'✅' if r.passed else '❌'} |")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")


class CampaignRunner:
    def __init__(self, device: Device, plant: Plant):
        self.engine = LoopEngine(device, plant)

    def run(self, testplan_path: str) -> CampaignResult:
        with open(testplan_path, encoding="utf-8") as f:
            plan = yaml.safe_load(f)

        result = CampaignResult(name=plan.get("name", "unnamed campaign"))
        requirements = plan.get("requirements", [])

        for scen in plan.get("scenarios", []):
            run = self.engine.run(setpoint=scen["setpoint"],
                                  duration=scen["duration"],
                                  dt=scen.get("dt", 0.001))
            metrics = step_metrics(run)
            checks = []
            for req in requirements:
                measured = metrics[req["metric"]]
                passed, bound = True, ""
                if "max" in req:
                    passed &= measured <= req["max"]
                    bound = f"<= {req['max']}"
                if "min" in req:
                    passed &= measured >= req["min"]
                    bound = (bound + " and " if bound else "") + f">= {req['min']}"
                checks.append(RequirementResult(
                    req_id=req.get("id", "REQ-?"),
                    description=req.get("description", ""),
                    metric=req["metric"], bound=bound,
                    measured=measured, passed=passed))
            result.scenario_results[scen["name"]] = checks
        return result
