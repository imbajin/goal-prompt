#!/usr/bin/env python3
"""Minimal provider-only reverse proxy for an isolated HugeGraph A/B arm."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request


HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}
MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 32 * 1024 * 1024


class LimitedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    _slots = threading.BoundedSemaphore(8)

    def process_request(self, request, client_address) -> None:
        if not self._slots.acquire(blocking=False):
            request.close()
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


def has_remote_input(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"file_id", "file_url", "image_url"} and item:
                return True
            if has_remote_input(item):
                return True
    elif isinstance(value, list):
        return any(has_remote_input(item) for item in value)
    return False


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        if self.path == "/policy":
            payload = json.dumps({
                "schema_version": 1,
                "identity": self.server.policy_identity,
                "provider_api_only": True,
                "public_answer_sources_denied": True,
                "forward_proxy_disabled": True,
            }, separators=(",", ":")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_error(405, "only the local policy endpoint supports GET")

    def do_POST(self) -> None:
        self.forward()

    def do_DELETE(self) -> None:
        self.send_error(405, "provider mutation endpoints are disabled")

    def do_PUT(self) -> None:
        self.send_error(405, "provider mutation endpoints are disabled")

    def do_CONNECT(self) -> None:
        self.send_error(405, "CONNECT is disabled")

    def forward(self) -> None:
        if self.headers.get("Authorization") != f"Bearer {self.server.client_token}":
            self.send_error(401, "invalid arm-local model token")
            return
        with self.server.request_lock:
            if self.server.request_count >= 120:
                self.send_error(429, "arm-local model request budget exhausted")
                return
            self.server.request_count += 1
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.path != "/v1/responses":
            self.send_error(403, "only model inference endpoints are allowed")
            return
        upstream = self.server.upstream.rstrip("/") + self.path[len("/v1"):]
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "invalid Content-Length")
            return
        if length < 0 or length > MAX_REQUEST_BYTES:
            self.send_error(413, "model request is too large")
            return
        body = self.rfile.read(length) if length else None
        try:
            request_json = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_error(400, "model request must be JSON")
            return
        forbidden_tools = {
            "web_search", "web_search_preview", "file_search", "computer_use",
            "computer_use_preview", "code_interpreter", "mcp", "image_generation",
        }
        tools = request_json.get("tools", []) if isinstance(request_json, dict) else []
        model = request_json.get("model", "") if isinstance(request_json, dict) else ""
        if (not isinstance(model, str) or model != self.server.allowed_model or
                "web_search_options" in request_json):
            self.send_error(403, "only the preregistered A/B model is allowed")
            return
        if has_remote_input(request_json.get("input")):
            self.send_error(403, "remote image/file inputs and uploaded file IDs are disabled")
            return
        if request_json.get("background") is True or request_json.get("store") is True:
            self.send_error(403, "background and stored responses are disabled")
            return
        request_json["store"] = False
        body = json.dumps(request_json, separators=(",", ":")).encode()
        if any(isinstance(tool, dict) and tool.get("type") in forbidden_tools
               for tool in tools if isinstance(tools, list)):
            self.send_error(403, "provider-hosted retrieval tools are disabled")
            return
        headers = {
            key: value for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP and key.lower() not in {"host", "content-length"}
        }
        headers["Content-Type"] = "application/json"
        headers["Authorization"] = f"Bearer {self.server.provider_key}"
        if self.server.upstream_mode == "chatgpt_codex":
            headers["ChatGPT-Account-Id"] = self.server.chatgpt_account_id
        request = urllib.request.Request(upstream, data=body, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(request, context=ssl.create_default_context(), timeout=900) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
                if len(payload) > MAX_RESPONSE_BYTES:
                    self.send_error(502, "model response exceeded the trusted byte limit")
                    return
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in HOP_BY_HOP and key.lower() != "content-length":
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as error:
            payload = error.read()
            self.send_response(error.code)
            for key, value in error.headers.items():
                if key.lower() not in HOP_BY_HOP and key.lower() != "content-length":
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        print("model-proxy", self.address_string(), fmt % args, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--upstream-mode", choices=("openai_api", "chatgpt_codex"),
                        default="openai_api")
    parser.add_argument("--policy-identity", required=True)
    parser.add_argument("--allowed-model", required=True)
    parser.add_argument("--client-token", required=True)
    args = parser.parse_args()
    parsed = urllib.parse.urlsplit(args.upstream)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise SystemExit("upstream must be a credential-free HTTPS URL")
    if args.upstream_mode == "chatgpt_codex" and (
            parsed.hostname != "chatgpt.com" or parsed.path.rstrip("/") != "/backend-api/codex"):
        raise SystemExit("chatgpt_codex upstream must be https://chatgpt.com/backend-api/codex")
    server = LimitedThreadingHTTPServer((args.listen, args.port), Handler)
    server.upstream = args.upstream
    server.policy_identity = args.policy_identity
    server.allowed_model = args.allowed_model
    server.client_token = args.client_token
    server.upstream_mode = args.upstream_mode
    if args.upstream_mode == "chatgpt_codex":
        server.provider_key = os.environ.get("CHATGPT_ACCESS_TOKEN")
        server.chatgpt_account_id = os.environ.get("CHATGPT_ACCOUNT_ID")
    else:
        server.provider_key = os.environ.get("OPENAI_API_KEY")
        server.chatgpt_account_id = None
    server.request_lock = threading.Lock()
    server.request_count = 0
    if not server.provider_key:
        raise SystemExit("trusted provider key is required")
    if args.upstream_mode == "chatgpt_codex" and not server.chatgpt_account_id:
        raise SystemExit("trusted ChatGPT account identity is required")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
