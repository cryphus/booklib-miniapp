"""Static dev server for the Mini App.

Plain `http.server` lets the browser cache ES modules, so edits do not show up until a
hard reload. This serves the same files with caching disabled and falls back to
index.html, which keeps deep links working during development.

    python devserver.py [port]

For production the app is served by nginx (see Dockerfile / nginx.conf).
"""

from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent.resolve()


class DevHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers_original()

    def end_headers_original(self) -> None:
        SimpleHTTPRequestHandler.end_headers(self)

    def send_head(self):
        path = self.translate_path(self.path)
        if not Path(path).exists() and "." not in Path(path).name:
            self.path = "/index.html"
        return SimpleHTTPRequestHandler.send_head(self)

    def log_message(self, fmt: str, *args) -> None:
        if "GET" in (args[0] if args else ""):
            return  # keep the console readable
        super().log_message(fmt, *args)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
    handler = partial(DevHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Remarka frontend: http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
