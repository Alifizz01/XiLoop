"""Out-of-process devices: firmware over TCP (PiL) or a real board over serial (HiL).

Both speak the same tiny line protocol, so one firmware works on every rung
of the ladder - native build, Renode/QEMU, real microcontroller:

    host -> device          device -> host
    R                       OK              reset controller state
    S <setpoint>            OK              new target
    P <name> <value>        OK | ERR ...    set a tunable parameter (e.g. P kp 2.0)
    T <measurement> <dt>    <command>       one control tick

ASCII, one request line, exactly one reply line, '\\n' terminated. Lock-step:
the plant only advances once the device has answered, so timing on the host
never corrupts the physics (the loop is as deterministic as the firmware).
"""
import socket

from xiloop.interfaces import Device


class DeviceError(RuntimeError):
    pass


class StreamDevice(Device):
    """Protocol logic. Subclasses provide _write(bytes) and _readline() -> bytes."""

    def __init__(self, params: dict | None = None):
        self.params = dict(params or {})

    def _cmd(self, line: str) -> str:
        self._write((line + "\n").encode("ascii"))
        reply = self._readline()
        if not reply:
            raise DeviceError(f"device did not answer {line!r} (timeout or disconnected)")
        reply = reply.decode("ascii", "replace").strip()
        if reply.startswith("ERR"):
            raise DeviceError(f"device rejected {line!r}: {reply}")
        return reply

    def reset(self) -> None:
        self._cmd("R")
        for name, value in self.params.items():
            self._cmd(f"P {name} {float(value):.9g}")

    def set_setpoint(self, setpoint: float) -> None:
        self._cmd(f"S {setpoint:.9g}")

    def step(self, measurement: float, dt: float) -> float:
        reply = self._cmd(f"T {measurement:.9g} {dt:.9g}")
        try:
            return float(reply)
        except ValueError:
            raise DeviceError(f"expected a number from the device, got {reply!r}") from None

    def close(self) -> None:
        pass


class SocketDevice(StreamDevice):
    """Firmware reachable over TCP: a native build of your C code, or a
    Renode/QEMU UART exposed as a server socket (see examples/firmware_pid)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5555,
                 params: dict | None = None, timeout: float = 2.0):
        super().__init__(params)
        try:
            self._sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as e:
            raise DeviceError(f"cannot reach firmware at {host}:{port} - is it running? ({e})") from None
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._rx = self._sock.makefile("rb")

    def _write(self, data: bytes) -> None:
        self._sock.sendall(data)

    def _readline(self) -> bytes:
        try:
            return self._rx.readline()
        except (TimeoutError, OSError):
            return b""

    def close(self) -> None:
        self._rx.close()
        self._sock.close()


class SerialDevice(StreamDevice):
    """A real microcontroller over USB-serial (true HiL). Needs pyserial."""

    def __init__(self, port: str, baud: int = 115200,
                 params: dict | None = None, timeout: float = 2.0, boot_wait: float = 2.0):
        try:
            import serial
        except ImportError:
            raise DeviceError("SerialDevice needs pyserial: pip install xiloop[hil]") from None
        super().__init__(params)
        try:
            self._ser = serial.Serial(port, baud, timeout=timeout)
        except serial.SerialException as e:
            raise DeviceError(f"cannot open {port}: {e}") from None
        # Opening the port resets most Arduino-style boards; wait for boot.
        import time
        time.sleep(boot_wait)
        self._ser.reset_input_buffer()

    def _write(self, data: bytes) -> None:
        self._ser.write(data)

    def _readline(self) -> bytes:
        return self._ser.readline()

    def close(self) -> None:
        self._ser.close()
