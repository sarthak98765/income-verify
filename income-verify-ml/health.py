import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from logger import custom_logger

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"status":"OK"}'
        self.send_response(200 if self.path == "/health" else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

def start_health_server(port: int) -> None:
    """Serve /health on `port` in the background. A port of 0 disables it."""
    if not port:
        return
    try:
        server = HTTPServer(("0.0.0.0", port), Handler)
    except OSError as e:
        custom_logger.warning(f"health | could not bind port {port}: {e}")
        return
    threading.Thread(target=server.serve_forever, daemon=True).start()
    custom_logger.info(f"health | probe listening on :{port}")
