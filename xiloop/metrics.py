"""Step-response metrics - the quantities requirements are written against."""
from xiloop.engine import LoopResult

METRICS = {
    "final": "final measured value",
    "steady_state_error": "|setpoint - final value|",
    "overshoot_pct": "peak beyond the setpoint, in % of the setpoint",
    "rise_time_s": "time from 10 % to 90 % of the setpoint",
    "settling_time_s": "time until the response stays inside a +/-2 % band",
    "peak_command": "largest |command| the device produced (actuator effort)",
}


def step_metrics(result: LoopResult) -> dict:
    t, sp = result.t, result.setpoint
    if not t:
        raise ValueError("empty run - duration must be at least one dt")
    final = result.measurement[-1]
    m = {
        "final": final,
        "steady_state_error": abs(sp - final),
        "overshoot_pct": 0.0,
        "rise_time_s": float("inf"),
        "settling_time_s": float("inf"),
        "peak_command": max(abs(c) for c in result.command),
    }
    if sp == 0:
        return m

    # Work on a normalised response (setpoint -> 1.0) so negative steps
    # are measured exactly like positive ones.
    y = [yi / sp for yi in result.measurement]
    m["overshoot_pct"] = max(0.0, (max(y) - 1.0) * 100.0)

    t10 = next((ti for ti, yi in zip(t, y) if yi >= 0.1), None)
    t90 = next((ti for ti, yi in zip(t, y) if yi >= 0.9), None)
    if t10 is not None and t90 is not None:
        m["rise_time_s"] = t90 - t10

    # settling time: first moment after which the response stays inside
    # a +/-2 % band around the setpoint until the end of the run
    if abs(y[-1] - 1.0) <= 0.02:
        outside = [ti for ti, yi in zip(t, y) if abs(yi - 1.0) > 0.02]
        dt = t[1] - t[0] if len(t) > 1 else 0.0
        m["settling_time_s"] = outside[-1] + dt if outside else 0.0
    return m
