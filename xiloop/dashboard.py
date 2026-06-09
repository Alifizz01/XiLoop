"""TuningDashboard - interactive tuning for any device/plant pair (v0.2).

Every time you move a slider the closed loop is re-run (a full campaign-grade
simulation takes well under a second) and the response + metrics redraw.
Tuning becomes: drag, look, done.

Usage (see examples/actuator_pid/tune.py):

    TuningDashboard(
        make_device=lambda kp, ki, kd: PIDDevice(PID(kp=kp, ki=ki, kd=kd)),
        make_plant=ActuatorPlant,
        params={"kp": (0.1, 10.0, 2.0), "ki": (0.0, 5.0, 1.0), "kd": (0.0, 0.5, 0.05)},
        setpoint=1.0, duration=3.0,
    ).show()

`params` maps slider name -> (min, max, initial). The dashboard never mutates
your objects: on each change it calls `make_device(**slider_values)` and
`make_plant()` fresh, so results are exactly reproducible in a campaign.

Requires matplotlib (install with `pip install -e .[plot]`).
"""
from xiloop.engine import LoopEngine
from xiloop.metrics import step_metrics


class TuningDashboard:
    def __init__(self, make_device, make_plant, params,
                 setpoint: float = 1.0, duration: float = 3.0, dt: float = 0.001):
        self.make_device = make_device
        self.make_plant = make_plant
        self.params = params
        self.setpoint = setpoint
        self.duration = duration
        self.dt = dt
        self._sliders = {}
        self._fig = None

    # ---- headless-friendly core (used by the UI and by tests) -------------
    def initial_values(self) -> dict:
        return {name: spec[2] for name, spec in self.params.items()}

    def compute(self, **values):
        """Run one closed loop with the given parameter values."""
        device = self.make_device(**values)
        plant = self.make_plant()
        run = LoopEngine(device, plant).run(self.setpoint, self.duration, self.dt)
        return run, step_metrics(run)

    @staticmethod
    def _fmt(m: dict) -> str:
        return (f"rise {m['rise_time_s']:.3f} s   "
                f"overshoot {m['overshoot_pct']:.1f} %   "
                f"sse {m['steady_state_error']:.4f}   "
                f"settle {m['settling_time_s']:.2f} s")

    # ---- UI ----------------------------------------------------------------
    def build_figure(self):
        import matplotlib.pyplot as plt
        from matplotlib.widgets import Slider

        n_sliders = len(self.params) + 1          # + setpoint
        slider_h = 0.045
        bottom = 0.08 + n_sliders * slider_h

        self._fig = plt.figure("XiLoop tuning dashboard", figsize=(9, 6))
        self._ax = self._fig.add_axes([0.09, bottom + 0.06, 0.88, 0.86 - bottom])

        run, m = self.compute(**self.initial_values())
        (self._line,) = self._ax.plot(run.t, run.measurement, lw=2, color="#0b5fa5")
        self._sp_line = self._ax.axhline(self.setpoint, ls="--", c="k", lw=1)
        self._ax.set_xlabel("time [s]")
        self._ax.set_ylabel("measurement")
        self._ax.set_title(self._fmt(m), fontsize=10)

        # parameter sliders
        for i, (name, (lo, hi, init)) in enumerate(self.params.items()):
            ax = self._fig.add_axes([0.18, 0.06 + i * slider_h, 0.66, 0.03])
            s = Slider(ax, name, lo, hi, valinit=init)
            s.on_changed(self._update)
            self._sliders[name] = s

        # setpoint slider (range scales with the initial setpoint)
        sp_hi = abs(self.setpoint) * 2 if self.setpoint else 1.0
        ax = self._fig.add_axes([0.18, 0.06 + len(self.params) * slider_h, 0.66, 0.03])
        self._sp_slider = Slider(ax, "setpoint", 0.0, sp_hi, valinit=self.setpoint)
        self._sp_slider.on_changed(self._update)
        return self._fig

    def _update(self, _event=None):
        self.setpoint = self._sp_slider.val
        values = {name: s.val for name, s in self._sliders.items()}
        run, m = self.compute(**values)
        self._line.set_data(run.t, run.measurement)
        self._sp_line.set_ydata([self.setpoint, self.setpoint])
        self._ax.relim()
        self._ax.autoscale_view()
        self._ax.set_title(self._fmt(m), fontsize=10)
        self._fig.canvas.draw_idle()

    def show(self):
        import matplotlib.pyplot as plt
        if self._fig is None:
            self.build_figure()
        plt.show()
