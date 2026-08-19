#!/usr/bin/env python3
"""Verify an arm's private services and deny public/forward-proxy access."""

from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def fetch_json(url: str) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": "hugegraph-ab-network-probe/1"})
    with urlopen(request, timeout=10) as response:
        if response.status < 200 or response.status >= 300:
            raise ValueError(f"HTTP {response.status} from {url}")
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object from {url}")
    return value


def fetch_health(url: str) -> None:
    request = Request(url, headers={"User-Agent": "hugegraph-ab-network-probe/1"})
    with urlopen(request, timeout=10) as response:
        if response.status < 200 or response.status >= 400:
            raise ValueError(f"private health endpoint failed: {url} HTTP {response.status}")


def assert_public_tcp_denied(host: str, port: int) -> None:
    try:
        with socket.create_connection((host, port), timeout=3):
            pass
    except OSError:
        return
    raise ValueError(f"public TCP unexpectedly reachable: {host}:{port}")


def assert_not_forward_proxy(base_url: str, api_key: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("model base URL must be HTTP(S)")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    connection: socket.socket | None = None
    try:
        connection = socket.create_connection((parsed.hostname, port), timeout=8)
        if parsed.scheme == "https":
            connection = ssl.create_default_context().wrap_socket(connection, server_hostname=parsed.hostname)
        connection.sendall(
            b"CONNECT github.com:443 HTTP/1.1\r\n"
            b"Host: github.com:443\r\n"
            + f"Authorization: Bearer {api_key}\r\n".encode()
            + f"Proxy-Authorization: Bearer {api_key}\r\n".encode()
            + b"Connection: close\r\n\r\n"
        )
        reply = bytearray()
        while b"\r\n" not in reply and len(reply) < 4096:
            chunk = connection.recv(min(512, 4096 - len(reply)))
            if not chunk:
                break
            reply.extend(chunk)
    except OSError:
        return
    finally:
        if connection is not None:
            connection.close()
    status_line = bytes(reply).split(b"\r\n", 1)[0]
    try:
        status = int(status_line.split(b" ", 2)[1]) if status_line.startswith((b"HTTP/1.1 ", b"HTTP/1.0 ")) else 0
    except (IndexError, ValueError) as exc:
        raise ValueError("model endpoint returned an invalid CONNECT response") from exc
    if not status:
        raise ValueError("model endpoint returned no valid CONNECT status line")
    if 200 <= status < 300:
        raise ValueError("model endpoint accepted a CONNECT tunnel to github.com")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-base-url", required=True)
    parser.add_argument("--policy-url", required=True)
    parser.add_argument("--policy-identity", required=True)
    parser.add_argument("--health-urls-json", required=True)
    args = parser.parse_args()
    try:
        policy = fetch_json(args.policy_url)
        expected = {
            "schema_version": 1,
            "identity": args.policy_identity,
            "provider_api_only": True,
            "public_answer_sources_denied": True,
            "forward_proxy_disabled": True,
        }
        if any(policy.get(key) != value for key, value in expected.items()):
            raise ValueError("model policy endpoint does not satisfy the reviewed contract")
        health_urls = json.loads(args.health_urls_json)
        if not isinstance(health_urls, list) or not health_urls or not all(isinstance(item, str) and item for item in health_urls):
            raise ValueError("private health URLs must be a non-empty string array")
        for url in health_urls:
            fetch_health(url)
        assert_public_tcp_denied("1.1.1.1", 443)
        assert_public_tcp_denied("github.com", 443)
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("authenticated CONNECT probe requires OPENAI_API_KEY")
        assert_not_forward_proxy(args.model_base_url, api_key)
        print("network policy probe: PASS")
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
