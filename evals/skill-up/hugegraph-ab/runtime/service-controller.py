#!/usr/bin/env python3
"""Create or clean one anonymous arm's private HugeGraph service topology."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any


RUNTIME_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get(
    "HG_AB_RUNTIME_PRIVATE_CONFIG", str(RUNTIME_DIR / "runtime-private.json"),
)).resolve()
MODEL_PROXY = RUNTIME_DIR / "model-proxy.py"
SERVER_IMAGE = "hugegraph/server:1.7.0"
PD_IMAGE = "hugegraph/pd:1.7.0"
STORE_IMAGE = "hugegraph/store:1.7.0"
PROXY_IMAGE = "python:3.12-slim"
PASSWORD = "hg-ab-isolated-admin"
DATA_MARKER = ".hg-ab-service-data.json"
SERVICE_LIMITS = ("--pids-limit", "512", "--memory", "4g", "--cpus", "4")
PROXY_LIMITS = ("--pids-limit", "128", "--memory", "256m", "--cpus", "1")
LOGIN_PROBE_CODE = r"""
import base64
import json
import sys
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


url, password = sys.argv[1:3]
basic = base64.b64encode(f"admin:{password}".encode()).decode()
body = json.dumps({
    "user_name": "admin", "user_password": password, "token_expire": 3600,
}).encode()
request = urllib.request.Request(
    url, data=body, method="POST",
    headers={"Content-Type": "application/json",
             "Authorization": f"Basic {basic}"},
)
try:
    with urllib.request.build_opener(NoRedirect).open(request, timeout=5) as response:
        status = response.status
        raw = response.read()
except urllib.error.HTTPError as error:
    print(f"http_status={error.code}", file=sys.stderr)
    retryable = error.code in {408, 425, 429} or error.code >= 500
    raise SystemExit(1 if retryable else 2)
except (OSError, urllib.error.URLError) as error:
    print(f"{type(error).__name__}: {error}", file=sys.stderr)
    raise SystemExit(1)
if status != 200:
    print(f"unexpected_status={status}", file=sys.stderr)
    raise SystemExit(1)
try:
    payload = json.loads(raw)
except (UnicodeDecodeError, json.JSONDecodeError) as error:
    print(f"invalid_json={type(error).__name__}", file=sys.stderr)
    raise SystemExit(2)
if not isinstance(payload, dict) or not payload.get("token"):
    print("missing_token", file=sys.stderr)
    raise SystemExit(2)
""".strip()


def run(argv: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["docker", *args], check=check)


def safe(value: str) -> str:
    rendered = re.sub(r"[^A-Za-z0-9_.-]", "-", value)
    if not rendered or rendered != value:
        raise ValueError("run id must already be Docker-name safe")
    return rendered


def names(run_id: str) -> dict[str, str]:
    prefix = f"hg-ab-svc-{safe(run_id)}"
    return {
        "network": f"hg-ab-net-{run_id}",
        "model": f"{prefix}-model",
        "pd": f"{prefix}-pd",
        "store": f"{prefix}-store",
        "server": f"{prefix}-server",
    }


def image_id(image: str) -> str:
    return docker("image", "inspect", "--format", "{{.Id}}", image).stdout.strip()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def container_ip(container: str, network: str) -> str:
    template = "{{(index .NetworkSettings.Networks \"" + network + "\").IPAddress}}"
    return docker("inspect", "--format", template, container).stdout.strip()


def request_from_proxy(proxy: str, url: str) -> bool:
    code = (
        "import sys,urllib.error,urllib.request; "
        "\ntry:\n r=urllib.request.urlopen(sys.argv[1],timeout=5); status=r.status\n"
        "except urllib.error.HTTPError as e:\n status=e.code\n"
        "raise SystemExit(0 if 200 <= status < 500 else 1)"
    )
    return docker("exec", proxy, "python3", "-c", code, url, check=False).returncode == 0


def wait_url(proxy: str, url: str, seconds: int) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if request_from_proxy(proxy, url):
            return
        time.sleep(3)
    raise ValueError(f"service health timeout: {url}")


def login_probe_from_proxy(proxy: str, url: str) -> tuple[int, str]:
    result = docker(
        "exec", proxy, "python3", "-c", LOGIN_PROBE_CODE, url, PASSWORD,
        check=False,
    )
    detail = (result.stderr or result.stdout).strip()[-500:]
    return result.returncode, detail.replace(PASSWORD, "<redacted>")


def wait_login(proxy: str, url: str, seconds: int) -> None:
    deadline = time.monotonic() + seconds
    last_detail = "no diagnostic"
    while time.monotonic() < deadline:
        returncode, detail = login_probe_from_proxy(proxy, url)
        if returncode == 0:
            return
        last_detail = detail or f"probe exited {returncode}"
        if returncode == 2:
            raise ValueError(f"service login rejected: {url}; {last_detail}")
        time.sleep(3)
    raise ValueError(f"service login timeout: {url}; last probe: {last_detail}")


def write_hstore_configs(data_dir: Path) -> tuple[Path, Path]:
    config_dir = data_dir / "service-config"
    config_dir.mkdir(parents=True, exist_ok=True)
    pd = config_dir / "pd-application.yml"
    store = config_dir / "store-application.yml"
    pd.write_text("""spring:\n  application:\n    name: hugegraph-pd\nmanagement:\n  endpoints:\n    web:\n      exposure:\n        include: \"*\"\nlogging:\n  config: 'file:./conf/log4j2.xml'\nlicense:\n  verify-path: ./conf/verify-license.json\n  license-path: ./conf/hugegraph.license\ngrpc:\n  port: 8686\n  host: pd\nserver:\n  port: 8620\npd:\n  data-path: /hugegraph-pd/pd_data\n  patrol-interval: 1800\n  initial-store-count: 1\n  initial-store-list: store:8500\nraft:\n  address: pd:8610\n  peers-list: pd:8610\nstore:\n  max-down-time: 172800\n  monitor_data_enabled: true\n  monitor_data_interval: 1 minute\n  monitor_data_retention: 1 day\npartition:\n  default-shard-count: 1\n  store-max-shard-count: 12\n""", encoding="utf-8")
    store.write_text("""pdserver:\n  address: pd:8686\nmanagement:\n  endpoints:\n    web:\n      exposure:\n        include: \"*\"\ngrpc:\n  host: store\n  port: 8500\n  netty-server:\n    max-inbound-message-size: 1000MB\nraft:\n  disruptorBufferSize: 1024\n  address: store:8510\n  max-log-file-size: 600000000000\n  snapshotInterval: 1800\nserver:\n  port: 8520\napp:\n  data-path: /hugegraph-store/storage\n  raft-path: /hugegraph-store/raft\nspring:\n  application:\n    name: store-node-grpc-server\n  profiles:\n    active: default\n    include: pd\nlogging:\n  config: 'file:./conf/log4j2.xml'\n  level:\n    root: info\n""", encoding="utf-8")
    return pd, store


def load_config() -> dict[str, Any]:
    value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if set(value) != {"provider_base_url", "model_policy_identity", "allowed_model"}:
        raise ValueError("runtime-private.json has unexpected keys")
    if not str(value["provider_base_url"]).startswith("https://"):
        raise ValueError("provider_base_url must be HTTPS")
    if not value["model_policy_identity"]:
        raise ValueError("model_policy_identity is required")
    if not isinstance(value["allowed_model"], str) or not value["allowed_model"]:
        raise ValueError("allowed_model is required")
    return value


def cleanup(run_id: str) -> None:
    item = names(run_id)
    failures: list[str] = []
    for key in ("server", "store", "pd", "model"):
        result = docker("rm", "-f", item[key], check=False)
        if result.returncode != 0 and "No such container" not in result.stderr:
            failures.append(f"container {item[key]}: {result.stderr.strip()}")
    result = docker("network", "rm", item["network"], check=False)
    if result.returncode != 0 and not re.search(
            r"(?:not found|No such network)", result.stderr, re.I):
        failures.append(f"network {item['network']}: {result.stderr.strip()}")
    if failures:
        raise ValueError("service cleanup failed: " + "; ".join(failures))


def start_model(item: dict[str, str], config: dict[str, Any]) -> None:
    provider_key = os.environ.get("HG_AB_MODEL_API_KEY")
    if not provider_key:
        raise ValueError("HG_AB_MODEL_API_KEY is required by the trusted model proxy")
    client_token = "hg-ab-client-" + item["model"].removeprefix("hg-ab-svc-").removesuffix("-model")
    docker(
        "run", "-d", "--name", item["model"], "--hostname", "model",
        "--network", item["network"], "--network-alias", "model",
        *PROXY_LIMITS,
        "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,size=64m",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--mount", f"type=bind,src={MODEL_PROXY},dst=/opt/model-proxy.py,readonly",
        "--env", f"OPENAI_API_KEY={provider_key}",
        str(config["proxy_image_id"]), "python3", "/opt/model-proxy.py",
        "--upstream", str(config["provider_base_url"]),
        "--policy-identity", str(config["model_policy_identity"]),
        "--allowed-model", str(config["allowed_model"]),
        "--client-token", client_token,
    )
    docker("network", "connect", "bridge", item["model"])
    wait_url(item["model"], "http://model:9000/policy", 30)


def write_rocksdb_graph_config(data_dir: Path, server_image_id: str) -> Path:
    source = docker(
        "run", "--rm", "--entrypoint", "cat", server_image_id,
        "/hugegraph-server/conf/graphs/hugegraph.properties",
    ).stdout
    if not re.search(r"(?m)^backend\s*=", source):
        raise ValueError("HugeGraph image graph config has no backend setting")
    rendered = re.sub(r"(?m)^backend\s*=.*$", "backend=rocksdb", source, count=1)
    # The 1.7 image defaults to HStore.  Leaving pd.peers in an otherwise
    # RocksDB config makes docker-entrypoint's storage wait block on a PD that
    # this standalone topology deliberately does not start.
    rendered = re.sub(r"(?m)^\s*pd\.peers\s*=.*\n?", "", rendered)
    for key, value in (
        ("rocksdb.data_path", "/hugegraph-server/rocksdb-data"),
        ("rocksdb.wal_path", "/hugegraph-server/rocksdb-wal"),
    ):
        pattern = rf"(?m)^\s*{re.escape(key)}\s*=.*$"
        if re.search(pattern, rendered):
            rendered = re.sub(pattern, f"{key}={value}", rendered, count=1)
        else:
            rendered += f"\n{key}={value}\n"
    config_dir = data_dir / "service-config"
    config_dir.mkdir(parents=True, exist_ok=True)
    graph_config = config_dir / "hugegraph.properties"
    graph_config.write_text(rendered, encoding="utf-8")
    return graph_config


def start_rocksdb(item: dict[str, str], data_dir: Path, server_image_id: str) -> list[str]:
    rocks = data_dir / "rocksdb"
    wal = data_dir / "rocksdb-wal"
    docker_flag = data_dir / "server-docker"
    graph_config = write_rocksdb_graph_config(data_dir, server_image_id)
    for path in (rocks, wal, docker_flag):
        path.mkdir(parents=True, exist_ok=True)
    docker(
        "run", "-d", "--name", item["server"], "--hostname", "hugegraph",
        "--network", item["network"], "--network-alias", "hugegraph",
        *SERVICE_LIMITS,
        "--mount", f"type=bind,src={rocks},dst=/hugegraph-server/rocksdb-data",
        "--mount", f"type=bind,src={wal},dst=/hugegraph-server/rocksdb-wal",
        "--mount", f"type=bind,src={docker_flag},dst=/hugegraph-server/docker",
        # enable-auth.sh edits the graph config during first initialization, so
        # mount the arm-local directory writable rather than bind-mounting one
        # file (sed cannot atomically replace a bind-mounted file).
        "--mount", "type=bind," +
                   f"src={graph_config.parent},dst=/hugegraph-server/conf/graphs",
        "--env", f"PASSWORD={PASSWORD}", server_image_id,
    )
    wait_url(item["model"], "http://hugegraph:8080/versions", 300)
    wait_login(item["model"], "http://hugegraph:8080/auth/login", 60)
    return ["http://model:9000/policy", "http://hugegraph:8080/versions"]


def start_hstore(item: dict[str, str], data_dir: Path, pd_image_id: str) -> list[str]:
    pd_conf, _store_conf = write_hstore_configs(data_dir)
    pd_data = data_dir / "pd-data"
    for path in (pd_data,):
        path.mkdir(parents=True, exist_ok=True)
    docker(
        "run", "-d", "--name", item["pd"], "--hostname", "pd",
        "--network", item["network"], "--network-alias", "pd",
        *SERVICE_LIMITS,
        "--mount", f"type=bind,src={pd_conf},dst=/hugegraph-pd/conf/application.yml,readonly",
        "--mount", f"type=bind,src={pd_data},dst=/hugegraph-pd/pd_data",
        "--env", "HG_PD_GRPC_HOST=pd",
        "--env", "HG_PD_RAFT_ADDRESS=pd:8610",
        "--env", "HG_PD_RAFT_PEERS_LIST=pd:8610",
        "--env", "HG_PD_INITIAL_STORE_LIST=store:8500",
        pd_image_id,
    )
    wait_url(item["model"], "http://pd:8620/actuator/health", 240)
    # Do not start stock Store/Server containers here.  The trusted oracle
    # packages and launches both from the candidate 1.7 workspace after the
    # Agent exits.  PD remains the only shared official infrastructure.
    return [
        "http://model:9000/policy", "http://pd:8620/actuator/health",
    ]


def prepare(case_id: str, run_id: str, data_dir: Path, output: Path, identity: str) -> None:
    config = load_config()
    config["proxy_image_id"] = image_id(PROXY_IMAGE)
    item = names(run_id)
    cleanup(run_id)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / DATA_MARKER).write_text(json.dumps({
        "case_id": case_id, "run_id": run_id, "service_config_identity": identity,
    }) + "\n", encoding="utf-8")
    docker("network", "create", "--internal", item["network"])
    try:
        start_model(item, config)
        if case_id == "server-hstore-graph-isolation":
            pd_image_id = image_id(PD_IMAGE)
            health = start_hstore(item, data_dir, pd_image_id)
            images = {"model-proxy": config["proxy_image_id"],
                      "hugegraph-pd": pd_image_id}
        else:
            server_image_id = image_id(SERVER_IMAGE)
            health = start_rocksdb(item, data_dir, server_image_id)
            images = {"model-proxy": config["proxy_image_id"],
                      "hugegraph-server": server_image_id}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "schema_version": 1,
            "case_id": case_id,
            "run_id": run_id,
            "fresh_state": True,
            "exclusive_data_root": True,
            "data_root": str(data_dir.resolve()),
            "service_config_identity": identity,
            "network": item["network"],
            "network_id": docker("network", "inspect", "--format", "{{.Id}}", item["network"]).stdout.strip(),
            "private_health_urls": health,
            "model_base_url": "http://model:9000/v1",
            "model_policy_url": "http://model:9000/policy",
            "model_policy_identity": config["model_policy_identity"],
            "allowed_model": config["allowed_model"],
            "provider_origin_sha256": hashlib.sha256(
                str(config["provider_base_url"]).encode()).hexdigest(),
            "service_image_ids": images,
            "service_artifact_ids": {
                "controller_sha256": file_sha256(Path(__file__).resolve()),
                "model_proxy_sha256": file_sha256(MODEL_PROXY),
            },
        }, indent=2) + "\n", encoding="utf-8")
    except BaseException:
        cleanup(run_id)
        raise


def reset(case_id: str, run_id: str, data_dir: Path, output: Path, identity: str) -> None:
    # The Agent may legitimately exercise its private HugeGraph service.  The
    # trusted oracle must therefore receive a new service/network/data phase,
    # not state left by the model under test.
    cleanup(run_id)
    marker = data_dir / DATA_MARKER
    expected_marker = {
        "case_id": case_id, "run_id": run_id, "service_config_identity": identity,
    }
    if not marker.is_file() or json.loads(marker.read_text(encoding="utf-8")) != expected_marker:
        raise ValueError("service data marker is missing or does not match this anonymous arm")
    if data_dir.is_dir():
        for child in data_dir.iterdir():
            if child.name == DATA_MARKER:
                continue
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
    prepare(case_id, run_id, data_dir, output, identity)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "reset", "cleanup"))
    parser.add_argument("case_id")
    parser.add_argument("run_id")
    parser.add_argument("data_dir")
    parser.add_argument("output")
    parser.add_argument("identity")
    args = parser.parse_args()
    if args.case_id not in {
        "toolchain-empty-graph-edit", "server-hstore-graph-isolation",
        "docs-graphs-api-version-truth",
    }:
        raise SystemExit("unknown case")
    try:
        if args.action == "cleanup":
            cleanup(args.run_id)
        elif args.action == "reset":
            reset(args.case_id, args.run_id, Path(args.data_dir), Path(args.output), args.identity)
        else:
            prepare(args.case_id, args.run_id, Path(args.data_dir), Path(args.output), args.identity)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
