"""Built-in plant models. Start with a second-order actuator (fin / servo);
users add their own by implementing Plant.step()."""
from dataclasses import dataclass

from xiloop.interfaces import Plant


@dataclass
class ActuatorPlant(Plant):
    """J*theta'' + b*theta' = Kt*u - a rotary actuator with inertia & damping."""
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
