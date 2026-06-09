"""HiLo — X-in-the-Loop, from software to hardware.

A lightweight framework that wires a *device under test* (your controller) to a
*plant model* (the simulated system), runs the closed loop at a fixed rate,
records telemetry, and verifies requirement-based test campaigns.
"""
from hilo.interfaces import Device, Plant
from hilo.engine import LoopEngine, LoopResult
from hilo.controllers import PID, PIDDevice
from hilo.plants import ActuatorPlant
from hilo.metrics import step_metrics
from hilo.campaign import CampaignRunner

__version__ = "0.1.0"
__all__ = [
    "Device", "Plant", "LoopEngine", "LoopResult",
    "PID", "PIDDevice", "ActuatorPlant",
    "step_metrics", "CampaignRunner",
]
