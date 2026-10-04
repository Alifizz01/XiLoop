"""XiLoop - X-in-the-Loop, from software to hardware.

A lightweight framework that wires a *device under test* (your controller) to a
*plant model* (the simulated system), runs the closed loop at a fixed rate,
records telemetry, and verifies requirement-based test campaigns.
"""
from xiloop.interfaces import Device, Plant
from xiloop.engine import LoopEngine, LoopResult
from xiloop.controllers import PID, PIDDevice
from xiloop.plants import ActuatorPlant, FirstOrderPlant, TransferFunctionPlant
from xiloop.metrics import step_metrics
from xiloop.campaign import CampaignRunner, CampaignResult
from xiloop.devices import SocketDevice, SerialDevice, DeviceError

__version__ = "1.0.0"
__all__ = [
    "Device", "Plant", "LoopEngine", "LoopResult",
    "PID", "PIDDevice", "SocketDevice", "SerialDevice", "DeviceError",
    "ActuatorPlant", "FirstOrderPlant", "TransferFunctionPlant",
    "step_metrics", "CampaignRunner", "CampaignResult",
]
