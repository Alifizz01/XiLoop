"""A user-written plant: simple DC motor (voltage in, speed out).

Physics (simplified, standard first-order motor model):
    current  i = (V - Ke*w) / R          # voltage minus back-EMF over resistance
    torque   T = Kt * i
    speed    J*dw/dt = T - b*w           # inertia accelerates, friction brakes
"""
from dataclasses import dataclass

from hilo import Plant


@dataclass
class DCMotorPlant(Plant):
    R: float = 1.0      # winding resistance [ohm]
    Ke: float = 0.10    # back-EMF constant [V*s/rad]
    Kt: float = 0.10    # torque constant [N*m/A]
    J: float = 0.01     # rotor inertia [kg*m^2]
    b: float = 0.001    # viscous friction
    V_max: float = 24.0 # supply voltage limit
    w: float = 0.0      # speed [rad/s]  <- the measurement

    def reset(self) -> None:
        self.w = 0.0

    def step(self, command: float, dt: float) -> float:
        V = max(-self.V_max, min(self.V_max, command))
        i = (V - self.Ke * self.w) / self.R
        torque = self.Kt * i
        self.w += (torque - self.b * self.w) / self.J * dt
        return self.w
