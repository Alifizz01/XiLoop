"""Step-response metrics - the quantities requirements are written against."""
from xiloop.engine import LoopResult


def step_metrics(result: LoopResult) -> dict:
    y = result.measurement
    t = result.t
    sp = result.setpoint
    final = y[-1]
    m = {
        "final": final,
        "steady_state_error": abs(sp - final),
        "overshoot_pct": 0.0,
        "rise_time_s": float("inf"),
    }
    if sp != 0:
        m["overshoot_pct"] = max(0.0, (max(y) - sp) / abs(sp) * 100.0)
        t10 = t90 = None
        for ti, yi in zip(t, y):
            if t10 is None and yi >= 0.1 * sp:
                t10 = ti
            if t90 is None and yi >= 0.9 * sp:
                t90 = ti
                break
        if t10 is not None and t90 is not None:
            m["rise_time_s"] = t90 - t10
    return m
