"""XiLoop Studio - native desktop window around the local REST API.

The API server runs in the background of this process (or is reused if one is
already listening), and the window is just a client of it: everything you
click is an HTTP call you could also make from a script.
"""
import json
import threading
import urllib.request


def _alive(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5) as r:
            return json.load(r).get("ok", False)
    except OSError:
        return False


class _Bridge:
    """The only thing the window does outside the API: native Save dialogs."""

    def save_file(self, name: str, text: str):
        import webview
        path = webview.windows[0].create_file_dialog(webview.SAVE_DIALOG, save_filename=name)
        if not path:
            return None
        path = path if isinstance(path, str) else path[0]
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return path


def main(port: int = 8765) -> None:
    import webview   # pywebview: Edge WebView2 on Windows, WebKit on macOS, GTK/Qt on Linux

    if not _alive(port):
        from xiloop.server import make_server
        srv = make_server(port)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.create_window("XiLoop Studio", f"http://127.0.0.1:{port}/",
                          width=1440, height=900, min_size=(1024, 680),
                          background_color="#E4E6E1", js_api=_Bridge())
    webview.start()


if __name__ == "__main__":
    main()
