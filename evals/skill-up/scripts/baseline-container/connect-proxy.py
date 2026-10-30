#!/usr/bin/env python3
"""精确 API 域名 CONNECT 代理；经过宿主既有 CONNECT 出口，不解密/记录载荷。"""
import http.server
import os
import select
import socket
import socketserver
from urllib.parse import urlsplit

ALLOWED = {"chatgpt.com", "api.openai.com", "auth.openai.com"}
UPSTREAM = urlsplit(os.environ["UPSTREAM_CONNECT_PROXY"])
if UPSTREAM.scheme != "http" or not UPSTREAM.hostname or UPSTREAM.username or UPSTREAM.password:
    raise SystemExit("上游必须为不含凭据的既有 HTTP CONNECT 代理")

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def do_CONNECT(self):
        upstream = None
        try:
            host, port = self.path.rsplit(":", 1)
            if host not in ALLOWED or port != "443":
                self.send_error(403, "Destination denied")
                return
            upstream = socket.create_connection((UPSTREAM.hostname, UPSTREAM.port or 80), 30)
            request = f"CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n"
            upstream.sendall(request.encode("ascii"))
            header = b""
            while not header.endswith(b"\r\n\r\n") and len(header) < 65536:
                piece = upstream.recv(1)
                if not piece:
                    raise OSError("upstream closed")
                header += piece
            if not header.startswith((b"HTTP/1.1 200 ", b"HTTP/1.0 200 ")):
                self.send_error(502, "API tunnel unavailable")
                return
            self.send_response(200, "Connection established")
            self.end_headers()
            self.wfile.flush()
            sockets = [self.connection, upstream]
            while True:
                readable, _, _ = select.select(sockets, [], [], 900)
                if not readable:
                    break
                for current in readable:
                    payload = current.recv(65536)
                    if not payload:
                        return
                    (upstream if current is self.connection else self.connection).sendall(payload)
        except (OSError, ValueError):
            pass
        finally:
            if upstream:
                upstream.close()
            self.close_connection = True

    def do_GET(self):
        self.send_error(405, "CONNECT only")

class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

Server(("0.0.0.0", 3128), Handler).serve_forever()
