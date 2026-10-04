"""Built-in plant models. Users add their own by implementing Plant.step().

Convention: numeric dataclass fields are tunable parameters (the GUI shows
them as inputs), except the ones listed in STATE, which reset() clears.
"""
from dataclasses import dataclass

from xiloop.interfaces import Plant


@dataclass
class ActuatorPlant(Plant):
    """J*theta'' + b*theta' = Kt*u - a rotary actuator with inertia & damping."""
    STATE = ("pos", "vel")
    J: float = 0.01     # inertia
    b: float = 0.10     # viscous damping
    Kt: float = 1.0     # gain
    u_max: float = 10.0
    pos: float = 0.0
    vel: float = 0.0

    def reset(self) -> None:
        self.pos = 0.0
        self.vel = 0.0

    def step(self, command: float, dt: float) -> float:
        u = max(-self.u_max, min(self.u_max, command))
        acc = (self.Kt * u - self.b * self.vel) / self.J
        self.vel += acc * dt
        self.pos += self.vel * dt
        return self.pos


@dataclass
class FirstOrderPlant(Plant):
    """tau*y' + y = K*u (+ dead time) - the generic process model: heaters,
    tanks, motor speed, anything that 'lags then levels off'."""
    STATE = ("y", "_buf")
    K: float = 2.0          # static gain
    tau: float = 0.5        # time constant [s]
    delay: float = 0.0      # dead time [s]
    u_max: float = 10.0
    y: float = 0.0
    _buf: list | None = None

    def reset(self) -> None:
        self.y = 0.0
        self._buf = []

    def step(self, command: float, dt: float) -> float:
        if self._buf is None:
            self.reset()
        self._buf.append(max(-self.u_max, min(self.u_max, command)))
        n_delay = round(self.delay / dt)
        u = self._buf.pop(0) if len(self._buf) > n_delay else 0.0
        self.y += (self.K * u - self.y) / self.tau * dt
        return self.y


def _poly(v) -> list:
    if isinstance(v, str):
        v = v.replace(",", " ").split()
    return [float(c) for c in (v if isinstance(v, (list, tuple)) else [v])]


@dataclass
class TransferFunctionPlant(Plant):
    """Any linear plant typed as G(s) = num(s) / den(s), no code needed.

    Coefficients in descending powers of s, e.g. 2 / (0.5 s + 1):
        num="2", den="0.5 1".   A mass-spring-damper 1/(m s^2 + c s + k): den="1 0.4 4".
    Simulated in controllable canonical form with RK4 (u held over each dt).
    """
    STATE = ("_x",)
    num: str = "2"
    den: str = "0.5 1"
    u_max: float = 10.0
    _x: list | None = None

    def __post_init__(self):
        b, a = _poly(self.num), _poly(self.den)
        while a and a[0] == 0:
            a.pop(0)
        if not a:
            raise ValueError("denominator is zero")
        n = len(a) - 1
        if len(b) > n + 1 or n == 0:
            raise ValueError("G(s) must be proper with order >= 1: deg(num) <= deg(den)")
        lead = a[0]                       # normalise so den is monic
        a = [c / lead for c in a]
        b = [0.0] * (n + 1 - len(b)) + [c / lead for c in b]
        self._n, self._a, self._D = n, a, b[0]
        # y = sum_i C_i x_i + D u with C_i = b_(n-i) - a_(n-i) * b0 (x_0 = lowest state)
        self._C = [b[n - i] - a[n - i] * b[0] for i in range(n)]
        self.reset()

    def reset(self) -> None:
        self._x = [0.0] * self._n

    def _f(self, x, u):
        dx = x[1:] + [u - sum(self._a[self._n - i] * x[i] for i in range(self._n))]
        return dx

    def step(self, command: float, dt: float) -> float:
        u = max(-self.u_max, min(self.u_max, command))
        x, f = self._x, self._f
        k1 = f(x, u)
        k2 = f([xi + dt / 2 * k for xi, k in zip(x, k1)], u)
        k3 = f([xi + dt / 2 * k for xi, k in zip(x, k2)], u)
        k4 = f([xi + dt * k for xi, k in zip(x, k3)], u)
        self._x = [xi + dt / 6 * (a + 2 * b + 2 * c + d)
                   for xi, a, b, c, d in zip(x, k1, k2, k3, k4)]
        return sum(c * xi for c, xi in zip(self._C, self._x)) + self._D * u
