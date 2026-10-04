"""Build devices and plants from plain dicts - the shared vocabulary of YAML
test plans, the CLI and the Studio GUI.

    plant:  {type: actuator, params: {J: 0.02}}
            {type: "examples.dc_motor.plant:DCMotorPlant"}      # any Plant class
    device: {type: pid,    params: {kp: 2, ki: 1, kd: 0.05}}
            {type: socket, host: 127.0.0.1, port: 5555, params: {kp: 2}}
            {type: serial, port: COM5, baud: 115200, params: {kp: 2}}
            {type: "mypkg.ctrl:MyDevice", params: {...}}         # any Device class
"""
import dataclasses
import importlib

from xiloop.controllers import PID, PIDDevice
from xiloop.interfaces import Device, Plant
from xiloop.devices import SerialDevice, SocketDevice
from xiloop.plants import ActuatorPlant, FirstOrderPlant, TransferFunctionPlant

PLANTS = {
    "actuator": ActuatorPlant,
    "first_order": FirstOrderPlant,
    "transfer_function": TransferFunctionPlant,
    "dc_motor": "examples.dc_motor.plant:DCMotorPlant",
}


def load_class(path: str, base: type):
    """'package.module:ClassName' -> the class, which must subclass `base`
    (so a plan or API call can never instantiate arbitrary callables)."""
    mod, sep, name = path.partition(":")
    if not sep:
        raise ValueError(f"expected 'module:Class', got {path!r}")
    cls = getattr(importlib.import_module(mod), name, None)
    if not (isinstance(cls, type) and issubclass(cls, base)):
        raise ValueError(f"{path!r} is not a {base.__name__} class")
    return cls


def plant_class(type_: str):
    cls = PLANTS.get(type_, type_)
    if isinstance(cls, str):
        if ":" not in cls:
            raise ValueError(f"unknown plant {type_!r} - use one of {list(PLANTS)} or 'module:Class'")
        cls = load_class(cls, Plant)
    return cls


def plant_params(cls) -> dict:
    """Tunable numeric parameters of a dataclass plant, with their defaults."""
    if not dataclasses.is_dataclass(cls):
        return {}
    state = set(getattr(cls, "STATE", ()))
    return {f.name: f.default for f in dataclasses.fields(cls)
            if f.name not in state and not f.name.startswith("_")
            and isinstance(f.default, (int, float, str))}


def _spec(spec) -> dict:
    return {"type": spec} if isinstance(spec, str) else dict(spec)


def build_plant(spec):
    spec = _spec(spec)
    return plant_class(spec["type"])(**spec.get("params", {}))


def build_device(spec):
    spec = _spec(spec)
    kind, params = spec.get("type", "pid"), spec.get("params", {})
    if kind == "pid":
        return PIDDevice(PID(**params))
    if kind == "socket":
        return SocketDevice(spec.get("host", "127.0.0.1"), int(spec.get("port", 5555)), params)
    if kind == "serial":
        return SerialDevice(spec["port"], int(spec.get("baud", 115200)), params)
    return load_class(kind, Device)(**params)
