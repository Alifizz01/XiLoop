"""Virtual board: a reference firmware speaking the XiLoop line protocol over TCP.

Use it to try PiL without a compiler or hardware (`xiloop firmware`), as a
template for your own port, or to check a SocketDevice setup end to end.
The C version of the same firmware lives in examples/firmware_pid/.
"""
import socketserver
import threading

from xiloop.controllers import PID


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        pid, sp = PID(), 0.0
        for raw in self.rfile:
            parts = raw.decode("ascii", "replace").split()
            if not parts:
                continue
            try:
                op = parts[0]
                if op == "T":
                    reply = f"{pid.update(sp, float(parts[1]), float(parts[2])):.9g}"
                elif op == "S":
                    sp, reply = float(parts[1]), "OK"
                elif op == "R":
                    pid.reset()
                    reply = "OK"
                elif op == "P" and parts[1] in ("kp", "ki", "kd", "out_max"):
                    setattr(pid, parts[1], float(parts[2]))
                    reply = "OK"
                else:
                    reply = f"ERR unknown command {raw.decode(errors='replace').strip()!r}"
            except (IndexError, ValueError):
                reply = "ERR malformed"
            self.wfile.write((reply + "\n").encode("ascii"))


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def start(port: int = 5555, host: str = "127.0.0.1") -> _Server:
    """Start the virtual board in a background thread; returns the server (call .shutdown())."""
    srv = _Server((host, port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def serve(port: int = 5555, host: str = "127.0.0.1") -> None:
    print(f"XiLoop virtual board listening on {host}:{port} (Ctrl+C to stop)")
    with _Server((host, port), _Handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
