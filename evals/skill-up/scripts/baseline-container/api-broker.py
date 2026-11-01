#!/usr/bin/env python3
"""可信 Responses broker：只有 broker 可读取既有认证；不记录正文或秘密。"""
import datetime
import hashlib
import http.server
import json
import os
from pathlib import Path
import socketserver
import sys
import threading
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlsplit

MODEL = "gpt-6-luna"
EFFORT = "xhigh"
UPSTREAM_URL = "https://chatgpt.com/backend-api/codex/responses"
AUTH_PATH = Path("/run/secrets/codex-auth.json")
lock = threading.Lock()
counters = {"allowed": 0, "denied": 0, "upstream_requests": 0}

def validate_payload(path, payload):
    if path != "/v1/responses":
        return False, "route_denied"
    if not isinstance(payload, dict) or payload.get("model") != MODEL:
        return False, "model_denied"
    if not isinstance(payload.get("reasoning"), dict) or payload["reasoning"].get("effort") != EFFORT:
        return False, "effort_denied"
    if payload.get("stream") is not True:
        return False, "stream_required"
    def external(value):
        if isinstance(value, dict):
            if value.get("type") in {"web_search", "web_search_preview", "file_search", "mcp", "computer", "computer_use_preview", "image_generation", "input_image", "input_file", "input_audio"}:
                return True
            return any(external(v) for v in value.values())
        return isinstance(value, list) and any(external(v) for v in value)
    def local_tools(tools):
        if not isinstance(tools, list):
            return False
        for tool in tools:
            if not isinstance(tool, dict):
                return False
            kind = tool.get("type")
            if kind == "namespace":
                if not local_tools(tool.get("tools")):
                    return False
            elif kind not in {"function", "custom"}:
                return False
        return True
    if not local_tools(payload.get("tools", [])) or external(payload.get("input", [])):
        return False, "external_tool_denied"
    return True, "allowed"

def digest(value):
    return hashlib.sha256(value).hexdigest()

def request_identity(headers):
    """Codex 0.164.0 uses hyphenated headers; never infer identity from cache keys."""
    metadata = {}
    raw = headers.get("x-codex-turn-metadata")
    if raw:
        try:
            metadata = json.loads(raw)
            if not isinstance(metadata, dict):
                raise ValueError("invalid_metadata")
        except (ValueError, TypeError):
            raise ValueError("identity_invalid_metadata") from None
    values = []
    sources = []
    for header, field in (("session-id", "session_id"), ("thread-id", "thread_id")):
        direct, fallback = headers.get(header), metadata.get(field)
        value = direct or fallback
        if not isinstance(value, str) or len(value) != 36:
            raise ValueError("identity_missing_or_invalid")
        try:
            if str(uuid.UUID(value)) != value.lower():
                raise ValueError("invalid_uuid")
        except ValueError:
            raise ValueError("identity_missing_or_invalid") from None
        if direct and fallback and direct != fallback:
            raise ValueError("identity_conflict")
        values.append(value)
        sources.append("header" if direct else "turn_metadata")
    return (*values, "+".join(sources))

def event(record):
    with lock:
        print(json.dumps({"timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), **record, "counts": dict(counters)}, sort_keys=True), flush=True)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *_):
        pass
    def reject(self, status, reason, model=None, effort=None, request_hash=None):
        with lock:
            counters["denied"] += 1
        event({"event": "denied", "source_ip": self.client_address[0], "reason": reason,
               "status": status, "model": model if model in (MODEL, "gpt-6.1-sol", "gpt-6.1-terra") else None,
               "effort": effort if effort in ("none", "low", "medium", "high", "xhigh", "max") else None,
               "request_sha256": request_hash})
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        body = json.dumps({"error": reason}).encode()
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True
    def do_POST(self):
        if self.path != "/v1/responses":
            self.reject(403, "route_denied")
            return
        if self.headers.get("Content-Encoding", "identity").lower() != "identity":
            self.reject(415, "request_encoding_denied")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 32 * 1024 * 1024:
                self.reject(413, "request_size_denied")
                return
            raw = self.rfile.read(size)
            payload = json.loads(raw)
        except (ValueError, OSError):
            self.reject(400, "invalid_json")
            return
        rhash = digest(raw)
        valid, reason = validate_payload(self.path, payload)
        if not valid:
            reasoning = payload.get("reasoning", {}) if isinstance(payload, dict) else {}
            self.reject(403, reason, payload.get("model") if isinstance(payload, dict) else None,
                        reasoning.get("effort") if isinstance(reasoning, dict) else None, rhash)
            return
        try:
            session, thread, identity_source = request_identity(self.headers)
        except ValueError as error:
            self.reject(403, str(error), MODEL, EFFORT, rhash)
            return
        # Connection-close is a transport choice, not evidence that headers were sent.
        response_started = False
        # 仅在通过模型/effort/route验证的真实请求内读取原认证；不复制到 Agent 或日志。
        try:
            auth = json.loads(AUTH_PATH.read_text())
            token = auth["tokens"]["access_token"]
            account = auth["tokens"]["account_id"]
            if not isinstance(token, str) or not token or not isinstance(account, str) or not account:
                raise ValueError("auth_unavailable")
            payload["store"] = False
            forwarded = json.dumps(payload, ensure_ascii=False).encode()
            headers = {"Authorization": "Bearer " + token, "ChatGPT-Account-Id": account,
                       "Content-Type": "application/json", "Accept": "text/event-stream",
                       "Accept-Encoding": "identity", "OpenAI-Beta": "responses=experimental",
                       "originator": "codex_cli_rs", "User-Agent": "codex_cli_rs/0.164.0 (Linux; aarch64)"}
            # 会话标识只前转、哈希记录，不把客户端任意header转给上游。
            headers["session-id"] = session
            headers["thread-id"] = thread
            upstream = os.environ["UPSTREAM_CONNECT_PROXY"]
            spec = urlsplit(upstream)
            if spec.scheme != "http" or spec.username or spec.password or not spec.hostname:
                raise ValueError("upstream_proxy_unavailable")
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({"https": upstream}), NoRedirect())
            request = urllib.request.Request(UPSTREAM_URL, data=forwarded, headers=headers, method="POST")
            with lock:
                counters["allowed"] += 1
                counters["upstream_requests"] += 1
            event({"event": "accepted", "source_ip": self.client_address[0], "model": MODEL,
                   "effort": EFFORT, "request_sha256": rhash,
                   "session_sha256": digest(session.encode()), "thread_sha256": digest(thread.encode()),
                   "identity_source": identity_source})
            with opener.open(request, timeout=450) as response:
                response_started = True
                self.send_response(response.status)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                read = getattr(response, "read1", response.read)
                while True:
                    piece = read(65536)
                    if not piece:
                        break
                    self.wfile.write(piece)
                    self.wfile.flush()
                event({"event": "completed", "source_ip": self.client_address[0],
                       "model": MODEL, "effort": EFFORT, "status": response.status,
                       "request_sha256": rhash, "session_sha256": digest(session.encode()),
                       "thread_sha256": digest(thread.encode()), "identity_source": identity_source})
        except urllib.error.HTTPError as error:
            # 上游错误正文/headers可能带身份信息，一律不返回或记录。
            event({"event": "upstream_error", "source_ip": self.client_address[0], "model": MODEL,
                   "effort": EFFORT, "status": error.code, "request_sha256": rhash})
            if not response_started:
                self.reject(502, "upstream_request_failed", MODEL, EFFORT, rhash)
            self.close_connection = True
        except Exception as error:
            event({"event": "broker_error", "source_ip": self.client_address[0],
                   "error_type": type(error).__name__, "request_sha256": rhash})
            if not response_started:
                self.reject(502, "broker_request_failed", MODEL, EFFORT, rhash)
            self.close_connection = True
    def do_GET(self):
        self.reject(403, "method_denied")
    do_HEAD = do_GET
    do_CONNECT = do_GET
    do_PUT = do_GET
    do_DELETE = do_GET
    do_OPTIONS = do_GET

class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        body = {"model": MODEL, "reasoning": {"effort": EFFORT}, "stream": True}
        assert validate_payload("/v1/responses", body)[0]
        for model in ("gpt-6.1-sol", "gpt-6.1-terra", "gpt-5.6-luna"):
            assert not validate_payload("/v1/responses", {**body, "model": model})[0]
        assert not validate_payload("/v1/responses", {**body, "reasoning": {"effort": "high"}})[0]
        assert not validate_payload("/v1/models", body)[0]
        assert not validate_payload("/v1/responses", {**body, "stream": False})[0]
        assert not validate_payload("/v1/responses", {**body, "reasoning": "xhigh"})[0]
        assert not validate_payload("/v1/responses", {**body, "tools": [{"type": "web_search"}]})[0]
        assert not validate_payload("/v1/responses", {**body, "tools": [{"type": "code_interpreter"}]})[0]
        assert not validate_payload("/v1/responses", {**body, "tools": [{"type": "future_remote_tool"}]})[0]
        assert validate_payload("/v1/responses", {**body, "tools": [{"type": "namespace", "tools": [{"type": "custom"}, {"type": "function"}]}]})[0]
        assert not validate_payload("/v1/responses", {**body, "input": [{"type": "input_image"}]})[0]
        sid = "00000000-0000-4000-8000-000000000001"
        tid = "00000000-0000-4000-8000-000000000002"
        assert request_identity({"session-id": sid, "thread-id": tid}) == (sid, tid, "header+header")
        assert request_identity({"x-codex-turn-metadata": json.dumps({"session_id": sid, "thread_id": tid})}) == (sid, tid, "turn_metadata+turn_metadata")
        for bad in ({}, {"session_id": sid, "thread_id": tid},
                    {"session-id": sid, "thread-id": "bad"},
                    {"session-id": sid, "thread-id": tid, "x-codex-turn-metadata": json.dumps({"session_id": tid})}):
            try:
                request_identity(bad)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid or missing identity accepted")
        print("PASS broker validation; no credential reads or model calls")
    else:
        Server(("0.0.0.0", 3128), Handler).serve_forever()
