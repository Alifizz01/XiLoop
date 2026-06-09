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
        "settling_time_s": float("inf"),
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

        # settling time: first moment after which the response stays inside
        # a +/-2 % band around the setpoint until the end of the run
        band = 0.02 * abs(sp)
        if abs(final - sp) <= band:
            last_outside = 0.0
            outside_seen = False
            for ti, yi in zip(t, y):
                if abs(yi - sp) > band:
                    last_outside = ti
                    outside_seen = True
            dt = t[1] - t[0] if len(t) > 1 else 0.0
            m["settling_time_s"] = (last_outside + dt) if outside_seen else 0.0
    return m
