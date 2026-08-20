#!/usr/bin/env python3
"""Assertions over artifacts produced by test-suite.sh."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SUITE_DIR = SCRIPT_DIR.parent
REPO_ROOT = SUITE_DIR.parents[2]
CASE_IDS = (
    "toolchain-empty-graph-edit",
    "server-hstore-graph-isolation",
    "docs-graphs-api-version-truth",
)


def load_suite_module():
    spec = importlib.util.spec_from_file_location("hugegraph_ab_suite", SCRIPT_DIR / "suite.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def docs_prompts() -> dict[str, bytes]:
    text = (REPO_ROOT / "docs" / "hugegraph-ab-test-prompts.zh-CN.md").read_text(encoding="utf-8")
    headings = {
        "toolchain-empty-graph-edit": "### 2.2 前端 Raw Request",
        "server-hstore-graph-isolation": "### 2.3 后端 Raw Request",
        "docs-graphs-api-version-truth": "### 2.4 文档 Raw Request",
    }
    result: dict[str, bytes] = {}
    for case_id, heading in headings.items():
        start = text.index(heading)
        fence = text.index("```text\n", start) + len("```text\n")
        end = text.index("```", fence)
        result[case_id] = text[fence:end].encode("utf-8")
    return result


def judge(case_id: str, evidence: dict[str, Any], root: Path) -> dict[str, Any]:
    evidence_path = root / f"bad-{case_id}.json"
    score_path = root / f"bad-{case_id}-score.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    subprocess.run([
        sys.executable,
        str(SCRIPT_DIR / "judge-run.py"),
        "--case",
        case_id,
        "--evidence",
        str(evidence_path),
        "--output",
        str(score_path),
    ], check=True)
    return json.loads(score_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    suite = load_suite_module()
    oracle_spec = importlib.util.spec_from_file_location(
        "hugegraph_ab_runtime_oracle_test",
        SUITE_DIR / "runtime" / "trusted" / "oracle-driver.py",
    )
    assert oracle_spec and oracle_spec.loader
    runtime_oracle = importlib.util.module_from_spec(oracle_spec)
    oracle_spec.loader.exec_module(runtime_oracle)
    service_spec = importlib.util.spec_from_file_location(
        "hugegraph_ab_service_controller_test",
        SUITE_DIR / "runtime" / "service-controller.py",
    )
    assert service_spec and service_spec.loader
    service_controller = importlib.util.module_from_spec(service_spec)
    service_spec.loader.exec_module(service_controller)
    service_calls: list[tuple[str, ...]] = []
    original_service_docker = service_controller.docker
    original_service_wait = service_controller.wait_url

    def fake_service_docker(*argv: str, check: bool = True) -> SimpleNamespace:
        service_calls.append(argv)
        if argv[:4] == ("run", "--rm", "--entrypoint", "cat"):
            return SimpleNamespace(stdout=(
                "backend=hstore\nserializer=binary\npd.peers=127.0.0.1:8686\n"
                "#rocksdb.data_path=/old\n#rocksdb.wal_path=/old\n"
            ), returncode=0, stderr="")
        return SimpleNamespace(stdout="", returncode=0, stderr="")

    service_controller.docker = fake_service_docker
    service_controller.wait_url = lambda *unused_args, **unused_kwargs: None
    service_root = root / "service-controller"
    service_root.mkdir()
    rocks_config = service_controller.write_rocksdb_graph_config(
        service_root / "rocks", "sha256:server-test",
    ).read_text(encoding="utf-8")
    assert "backend=rocksdb" in rocks_config
    assert "pd.peers=" not in rocks_config
    assert "rocksdb.data_path=/hugegraph-server/rocksdb-data" in rocks_config
    assert "rocksdb.wal_path=/hugegraph-server/rocksdb-wal" in rocks_config
    service_controller.start_rocksdb(
        {
            "network": "net", "server": "server", "model": "model",
            "hugegraph": "hugegraph",
        },
        service_root / "rocks-start", "sha256:server-test",
    )
    rocks_run = next(
        call for call in service_calls
        if call[:2] == ("run", "-d") and "server" in call
    )
    assert f"PASSWORD={service_controller.PASSWORD}" in rocks_run
    assert any(
        value.startswith("type=bind,") and
        "dst=/hugegraph-server/conf/graphs" in value and
        "readonly" not in value
        for value in rocks_run
    )
    assert any("dst=/hugegraph-server/rocksdb-data" in value for value in rocks_run)
    assert any("dst=/hugegraph-server/rocksdb-wal" in value for value in rocks_run)
    service_controller.start_hstore(
        {"network": "net", "pd": "pd", "model": "model"},
        service_root / "hstore", "sha256:pd-test",
    )
    pd_run = next(call for call in service_calls if call[:2] == ("run", "-d") and "pd" in call)
    for expected in (
        "HG_PD_GRPC_HOST=pd", "HG_PD_RAFT_ADDRESS=pd:8610",
        "HG_PD_RAFT_PEERS_LIST=pd:8610", "HG_PD_INITIAL_STORE_LIST=store:8500",
    ):
        assert expected in pd_run
    service_controller.docker = original_service_docker
    service_controller.wait_url = original_service_wait
    for statement in (
        "1.8.0 has not been officially released",
        "1.8.0 hasn't been officially released",
        "1.8.0 尚未有正式发布版本",
        "1.8 不是正式发布版本",
    ):
        assert not runtime_oracle.affirmatively_claims_released_18(statement)
    assert not runtime_oracle.affirmatively_claims_release(
        "1.5.0 isn't officially released", "1.5.0",
    )
    assert not runtime_oracle.affirmatively_claims_release(
        "There is no official 1.5.0 release", "1.5.0",
    )
    assert not runtime_oracle.affirmatively_claims_release(
        "1.5.0 was never released", "1.5.0",
    )
    assert runtime_oracle.affirmatively_claims_release(
        "1.5.0 is an official release", "1.5.0",
    )
    assert runtime_oracle.named_validation_overclaim(
        "docs-graphs-api-version-truth",
        "Hugo build、链接检查与 API smoke 均已通过",
        {"site_quality": False, "api_behavior": False},
    )
    heading_contract = runtime_oracle.version_matrix_contract("""
## 1.5.0
GET /graphs/{graph}
Expected status: 200
POST /graphs/{graph}
Content-Type: text/plain; properties; backend=rocksdb; serializer=binary
Expected status: 200
DELETE /graphs/{graph}?confirm_message=I'm sure
Expected status: 204
## 1.7.0
GET /graphspaces/{graphspace}/graphs/{graph}; Expected status: 200
POST /graphspaces/{graphspace}/graphs/{graph}; application/json; Authorization: Bearer; gremlin.graph=HugeFactoryAuthProxy; backend=rocksdb,hstore; serializer=binary; store=demo; Expected status: 201
Auth-enabled required; non-auth creator NPE.
DELETE /graphspaces/{graphspace}/graphs/{graph}?confirm_message=I'm sure; Expected status: 204
## master post-1.7
GET /graphspaces/{graphspace}/graphs/{graph}; Expected status: 200
POST /graphspaces/{graphspace}/graphs/{graph}; application/json; Authorization: Bearer; gremlin.graph=HugeFactoryAuthProxy; backend=rocksdb,hstore; serializer=binary; store=demo; Expected status: 201
Non-auth creator anonymous fix, not included in 1.7.
DELETE /graphspaces/{graphspace}/graphs/{graph}?confirm_message=I'm sure; Expected status: 204
    """)
    assert all(all(values) for values in heading_contract.values())
    split_backend_contract = runtime_oracle.version_matrix_contract("""
## 1.5.0
GET /graphs/{graph} 200
POST /graphs/{graph} text/plain properties backend=rocksdb serializer=binary 200
DELETE /graphs/{graph}?confirm_message=yes 204
## 1.7.0 reference
GET /graphspaces/{graphspace}/graphs/{graph} 200
POST /graphspaces/{graphspace}/graphs/{graph} application/json Authorization Bearer gremlin.graph=HugeFactoryAuthProxy backend=rocksdb serializer=binary store=a 201
POST /graphspaces/{graphspace}/graphs/{graph} application/json Authorization Bearer gremlin.graph=HugeFactoryAuthProxy backend=hstore serializer=binary store=b 201
auth-enabled supported; non-auth creator NPE
DELETE /graphspaces/{graphspace}/graphs/{graph}?confirm_message=yes 204
## 1.7.0 examples
The two backend examples above are independently copyable.
## master post-1.7
GET /graphspaces/{graphspace}/graphs/{graph} 200
POST /graphspaces/{graphspace}/graphs/{graph} application/json Authorization Bearer gremlin.graph=HugeFactoryAuthProxy backend=rocksdb serializer=binary store=a 201
POST /graphspaces/{graphspace}/graphs/{graph} application/json Authorization Bearer gremlin.graph=HugeFactoryAuthProxy backend=hstore serializer=binary store=b 201
non-auth creator anonymous fix not included in 1.7
DELETE /graphspaces/{graphspace}/graphs/{graph}?confirm_message=yes 204
""")
    assert all(all(values) for values in split_backend_contract.values())
    assert runtime_oracle.claims_fix_in_17("The creator fix was already in 1.7.0")
    assert runtime_oracle.claims_fix_in_17("The non-auth creator NPE was resolved in 1.7.0")
    assert runtime_oracle.claims_fix_in_17("1.7.0 已解决非鉴权 creator NPE")
    assert not runtime_oracle.claims_fix_in_17("The creator fix was not included in 1.7.0")
    assert not runtime_oracle.claims_fix_in_17("The creator fix isn't in 1.7.0")
    assert not runtime_oracle.claims_fix_in_17("1.7.0 不包含该修复")
    assert not runtime_oracle.claims_fix_in_17("No creator fix exists in 1.7.0")
    assert not runtime_oracle.claims_fix_in_17("The creator fix never landed in 1.7.0")
    assert not runtime_oracle.claims_fix_in_17("The creator fix is absent in 1.7.0")
    assert runtime_oracle.claims_fix_in_17("1.7.0 ships with the creator repair")
    wrong_status = runtime_oracle.version_matrix_contract("""
## 1.5.0
GET /graphs/{graph}; Expected status: 204
POST /graphs/{graph}; text/plain; properties; backend=rocksdb; serializer=binary; Expected status: 200
DELETE /graphs/{graph}?confirm_message=I'm sure; Expected status: 204
## 1.7.0
GET /graphspaces/{graphspace}/graphs/{graph}; Expected status: 200
POST /graphspaces/{graphspace}/graphs/{graph}; application/json; Authorization: Bearer; gremlin.graph=HugeFactoryAuthProxy; backend=rocksdb,hstore; serializer=binary; store=demo; Expected status: 201
Auth-enabled required; non-auth creator NPE.
DELETE /graphspaces/{graphspace}/graphs/{graph}?confirm_message=I'm sure; Expected status: 204
## master post-1.7
GET /graphspaces/{graphspace}/graphs/{graph}; Expected status: 200
POST /graphspaces/{graphspace}/graphs/{graph}; application/json; Authorization: Bearer; gremlin.graph=HugeFactoryAuthProxy; backend=rocksdb,hstore; serializer=binary; store=demo; Expected status: 201
Non-auth creator anonymous fix, not included in 1.7.
DELETE /graphspaces/{graphspace}/graphs/{graph}?confirm_message=I'm sure; Expected status: 204
""")
    assert not all(wrong_status["1.5"])
    snapshot_root = root / "oracle-snapshot"
    snapshot_root.mkdir()
    (snapshot_root / "existing.txt").write_text("before", encoding="utf-8")
    before_snapshot = runtime_oracle.source_snapshot([snapshot_root])
    (snapshot_root / "new-source.js").write_text("export default true", encoding="utf-8")
    assert not runtime_oracle.source_snapshot_unchanged(
        before_snapshot, runtime_oracle.source_snapshot([snapshot_root]),
    )
    (snapshot_root / "new-source.js").unlink()
    dist = snapshot_root / "hugegraph-store/apache-hugegraph-store-incubating-1.7.0"
    dist.mkdir(parents=True)
    (dist / "generated.txt").write_text("before", encoding="utf-8")
    dist_before = runtime_oracle.source_snapshot([snapshot_root])
    (dist / "generated.txt").write_text("after", encoding="utf-8")
    assert runtime_oracle.source_snapshot_unchanged(
        dist_before, runtime_oracle.source_snapshot([snapshot_root]),
    )
    hubble_root = snapshot_root / "hugegraph-hubble"
    hubble_root.mkdir()
    hubble_before = runtime_oracle.source_snapshot([snapshot_root])
    (hubble_root / "apache-hugegraph-hubble-incubating-1.7.0.tar.gz").write_bytes(b"generated")
    (hubble_root / "apache-hugegraph-hubble-incubating-1.7.0").mkdir()
    (hubble_root / "apache-hugegraph-hubble-incubating-1.7.0/conf").mkdir()
    (hubble_root / "apache-hugegraph-hubble-incubating-1.7.0/conf/runtime.properties").write_text(
        "generated", encoding="utf-8")
    copied_hubble = hubble_root / "hubble-dist/apache-hugegraph-hubble-incubating-1.7.0"
    copied_hubble.mkdir(parents=True)
    (copied_hubble / "generated.txt").write_text("generated", encoding="utf-8")
    assert runtime_oracle.source_snapshot_unchanged(
        hubble_before, runtime_oracle.source_snapshot([snapshot_root]),
    )
    resources = snapshot_root / "module/src/main/resources"
    resources.mkdir(parents=True)
    (resources / "version.properties").write_text("1.7.0", encoding="utf-8")
    resources_before = runtime_oracle.source_snapshot([snapshot_root])
    (resources / "version.properties").write_text("1.8.0", encoding="utf-8")
    assert not runtime_oracle.source_snapshot_unchanged(
        resources_before, runtime_oracle.source_snapshot([snapshot_root]),
    )
    hidden_build = snapshot_root / "module/src/feature/build/runtime-fix.ts"
    hidden_build.parent.mkdir(parents=True)
    hidden_build.write_text("export default true", encoding="utf-8")
    assert str(hidden_build.absolute()) in runtime_oracle.source_snapshot([snapshot_root])
    hidden_modules = snapshot_root / "src/node_modules/runtime-fix.js"
    hidden_modules.parent.mkdir(parents=True)
    hidden_modules.write_text("export default true", encoding="utf-8")
    hidden_archive = snapshot_root / "src/runtime-fix.zip"
    hidden_archive.write_bytes(b"not generated")
    hidden_dist = snapshot_root / "src/apache-x-hubble-v1.2.3/runtime-fix.js"
    hidden_dist.parent.mkdir(parents=True)
    hidden_dist.write_text("export default true", encoding="utf-8")
    tightened = runtime_oracle.source_snapshot([snapshot_root])
    assert str(hidden_modules.absolute()) in tightened
    assert str(hidden_archive.absolute()) in tightened
    assert str(hidden_dist.absolute()) in tightened
    assert runtime_oracle.hidden_cross_graph_leak({
        "testPutIsolation": "HG_AB_CROSS_GRAPH_LEAK: visible in B",
    })
    assert not runtime_oracle.hidden_cross_graph_leak({
        "testPutIsolation": "AssertionError: expected value was missing",
    })
    interrupted_child_pid = root / "interrupted-child.pid"
    interrupter = threading.Timer(0.5, os.kill, args=(os.getpid(), signal.SIGINT))
    interrupter.start()
    try:
        suite.run_process([
            sys.executable, "-c",
            "import os,pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)",
            str(interrupted_child_pid),
        ], timeout_seconds=10)
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("run_process swallowed an interrupt")
    finally:
        interrupter.cancel()
        interrupter.join()
    assert interrupted_child_pid.is_file()
    child_pid = int(interrupted_child_pid.read_text(encoding="utf-8"))
    try:
        os.kill(child_pid, 0)
    except ProcessLookupError:
        pass
    else:
        raise AssertionError("interrupted child process group remained alive")

    original_service_action = suite.run_service_action
    original_build_parser = suite.build_parser
    cleanup_output = root / "cleanup-registry" / "service-attestation.json"
    cleanup_output.parent.mkdir()
    signal_child_pid = root / "signal-child.pid"
    cleanup_calls: list[str] = []

    def signal_scenario(_unused_args: Any) -> None:
        suite.register_service_cleanup(
            root / "harness", root / "spec", "toolchain-empty-graph-edit", "arm-sigterm",
            root / "data", cleanup_output, 10,
        )
        suite.run_process([
            sys.executable, "-c",
            "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',\"import os,pathlib,signal,sys,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)\",sys.argv[1]]); time.sleep(30)",
            str(signal_child_pid),
        ], timeout_seconds=10)

    fake_args = SimpleNamespace(func=signal_scenario)
    suite.build_parser = lambda: SimpleNamespace(parse_args=lambda: fake_args)
    suite.run_service_action = lambda *unused_args, **unused_kwargs: cleanup_calls.append("cleanup")
    terminator = threading.Timer(0.5, os.kill, args=(os.getpid(), signal.SIGTERM))
    terminator.start()
    with contextlib.redirect_stderr(io.StringIO()):
        assert suite.main() == 128 + signal.SIGTERM
    terminator.join()
    assert cleanup_calls == ["cleanup"] and signal_child_pid.is_file()
    signal_child = int(signal_child_pid.read_text(encoding="utf-8"))
    child_deadline = time.monotonic() + 2
    while time.monotonic() < child_deadline:
        try:
            os.kill(signal_child, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("SIGTERM left the TERM-ignoring grandchild alive")
    assert not suite.ACTIVE_SERVICE_CLEANUPS
    suite.build_parser = original_build_parser
    suite.register_service_cleanup(
        root / "harness", root / "spec", "toolchain-empty-graph-edit", "arm-cleanup-fail",
        root / "data", cleanup_output, 10,
    )

    def fail_cleanup(*unused_args: Any, **unused_kwargs: Any) -> None:
        raise suite.SuiteError("synthetic cleanup failure")

    suite.run_service_action = fail_cleanup
    assert suite.drain_service_cleanups()
    cleanup_failure = json.loads(
        (cleanup_output.parent / "service-cleanup-error.json").read_text(encoding="utf-8"),
    )
    assert cleanup_failure["failure_kind"] == "service_cleanup_error"
    suite.run_service_action = original_service_action
    secret_template = root / "fifo-secret-eval.yaml"
    secret_template.write_text(
        f"env:\n  OPENAI_API_KEY: {suite.RUNTIME_MODEL_KEY_MARKER}\n", encoding="utf-8",
    )
    fake_skill_up = root / "fifo-skill-up.py"
    fake_skill_up.write_text(
        "#!/usr/bin/env python3\n"
        "import os,pathlib,sys\n"
        "payload=pathlib.Path(sys.argv[2]).read_text()\n"
        "raise SystemExit(0 if os.environ['EXPECTED_SECRET'] in payload else 2)\n",
        encoding="utf-8",
    )
    fake_skill_up.chmod(0o700)
    fifo_env = os.environ.copy()
    fifo_env["EXPECTED_SECRET"] = "deterministic-test-secret"
    fifo_result = suite.run_skill_up_secret_config(
        fake_skill_up, "validate", secret_template, "deterministic-test-secret", [],
        env=fifo_env, timeout_seconds=10,
    )
    assert fifo_result.returncode == 0
    assert "deterministic-test-secret" not in secret_template.read_text(encoding="utf-8")
    assert not list(root.glob(".eval-secret-*.yaml"))
    assert suite.attested_runtime_failure({"executor_exit_code": 125, "wrapper_failure_kind": "copy_back_error"})
    assert suite.attested_runtime_failure({"executor_exit_code": 126, "wrapper_failure_kind": None})
    assert suite.attested_runtime_failure({"executor_exit_code": 2, "wrapper_failure_kind": None})
    assert suite.attested_model_failure({"executor_exit_code": 10, "wrapper_failure_kind": None})
    assert not suite.attested_runtime_failure({"executor_exit_code": 10, "wrapper_failure_kind": None})
    prompt_environment = suite.prompt_environment_block(SimpleNamespace(
        runtime="opensandbox", sandbox_template="test-template", reasoning_effort="medium",
        opensandbox_base_url="https://opensandbox.example.invalid",
        model_base_url="https://model.example.invalid/v1",
        model_policy_url="https://model.example.invalid/policy",
        model_policy_identity="policy-v1", model_egress_target="model.example.invalid",
    ))
    assert "wrap_socket" in prompt_environment and "set_tunnel" not in prompt_environment
    prompt_attestation_path = root / "prompt-runtime-attestation.json"
    prompt_attestation = {
        "schema_version": 1, "runtime": "opensandbox", "sandbox_template": "test-template",
        "model": "test-model", "reasoning_effort": "medium",
        "model_base_url": "https://model.example.invalid/v1",
        "model_egress_target": "model.example.invalid",
        "model_policy_url": "https://model.example.invalid/policy",
        "model_policy_identity": "policy-v1", "provider_proxy_only": True,
        "opensandbox_base_url": "https://opensandbox.example.invalid",
        "public_answer_sources_denied": True, "connectivity_probe_required": True,
        "control_plane_authenticated": True, "sandbox_image_id": "sha256:sandbox-test",
        "model_auth_identity": "test-service-account",
        "opensandbox_auth_identity": "test-opensandbox-account",
    }
    prompt_attestation_path.write_text(json.dumps(prompt_attestation), encoding="utf-8")
    validated_attestation = suite.validate_prompt_runtime_attestation(SimpleNamespace(
        runtime_attestation=str(prompt_attestation_path), sandbox_template="test-template",
        model="test-model", reasoning_effort="medium",
        opensandbox_base_url="https://opensandbox.example.invalid",
        model_base_url="https://model.example.invalid/v1",
        model_egress_target="model.example.invalid",
        model_policy_url="https://model.example.invalid/policy",
        model_policy_identity="policy-v1",
    ))
    assert validated_attestation["control_plane_authenticated"] is True

    # The checked cases are exact copies of the active-truth Raw Requests.
    expected = docs_prompts()
    for case_id in CASE_IDS:
        actual = suite.extract_prompt(SUITE_DIR / "cases" / f"{case_id}.yaml")
        assert actual == expected[case_id], f"Raw Request drift: {case_id}"
    eval_text = (SUITE_DIR / "eval.yaml").read_text(encoding="utf-8")
    assert re.search(r"benchmark:\s*\n\s+enabled:\s*false", eval_text)
    assert eval_text.count("hugegraph-ab/cases/") == 3

    sealed_ledger = json.loads((root / "sealed-root/cohorts/sealed-pilot/ledger.json").read_text(encoding="utf-8"))
    assert sealed_ledger["sealed"] is True and len(sealed_ledger["pairs"]) == 3
    assert [item["planned_prompt_order"] for item in sealed_ledger["pairs"]] == ["ab", "ba", "ab"]
    sealed_pair = root / "sealed-root/pairs/toolchain-empty-graph-edit/pilot-01"
    sealed_manifest = json.loads((sealed_pair / "manifest.json").read_text(encoding="utf-8"))
    suite.require_sealed_cohort_plan(sealed_pair, sealed_manifest, "prompt", "ab")
    try:
        suite.require_sealed_cohort_plan(sealed_pair, sealed_manifest, "prompt", "ba")
    except suite.SuiteError as exc:
        assert "differs" in str(exc)
    else:
        raise AssertionError("sealed cohort accepted an unplanned Prompt order")

    for case_id in CASE_IDS:
        pair_root = root / "pairs" / case_id / "fake-01"
        manifest = json.loads((pair_root / "manifest.json").read_text(encoding="utf-8"))
        mapping = json.loads((pair_root / "private" / "mapping.json").read_text(encoding="utf-8"))
        assert manifest["isolation"] == {
            "workspace": True,
            "home": True,
            "session": True,
            "data": True,
            "variant_labels_absent_from_arm_paths": True,
        }
        assert len(set(mapping["roles"].values())) == 2
        prompt_hashes = set()
        source_hashes = set()
        evidence_hashes = set()
        for arm_id in mapping["roles"].values():
            assert not re.search(r"with|without|control|treatment", arm_id)
            arm = pair_root / "arms" / arm_id
            request = arm / "prompt" / "session" / "raw-request.txt"
            prompt_hashes.add(suite.digest_bytes(request.read_bytes()))
            for stage in ("prompt", "execution"):
                workspace = arm / stage / "workspace"
                assert not any(path.name == ".git" for path in workspace.rglob(".git"))
                assert not (workspace / "private" / "mapping.json").exists()
                assert not any("oracle" in path.name or "judge" in path.name for path in workspace.rglob("*"))
                evidence_hashes.add(suite.tree_digest(workspace / "version-evidence"))
                if stage == "prompt":
                    source_hashes.add(suite.tree_digest(workspace, exclude_evidence=True))
            goal = arm / "execution" / "session" / "generated-goal.txt"
            response = arm / "prompt" / "response.txt"
            assert goal.read_bytes() == response.read_bytes(), "response was not forwarded verbatim"
            score = json.loads((arm / "execution" / "artifacts" / "score.json").read_text(encoding="utf-8"))
            run = json.loads((arm / "execution" / "artifacts" / "run.json").read_text(encoding="utf-8"))
            assert score["score"] == 100 and score["completed"] is True
            assert score["anonymous_run_id"] == arm_id
            assert score["run_binding"] == run["run_binding"]
            forged = json.loads((arm / "execution" / "agent-artifacts" / "score.json").read_text(encoding="utf-8"))
            assert forged == {"score": 999, "forged": True}
            assert run["source_before_sha256"] == manifest["source_sha256"]
        assert len(prompt_hashes) == 1
        assert source_hashes == {manifest["source_sha256"]}
        assert evidence_hashes == {manifest["version_evidence_sha256"]}

    # Synthetic bad samples prove caps and critical failures.
    toolchain_bad = judge("toolchain-empty-graph-edit", {
        "case_id": "toolchain-empty-graph-edit",
        "trusted_oracle": True,
        "checks": {"version_truth": True},
        "facts": {"visual_only": True},
        "claims": {"complete": True},
    }, root)
    assert toolchain_bad["score"] <= 40 and "completion_claim_without_persistence" in toolchain_bad["critical_failures"]

    server_checks = {name: True for name in (
        "put_isolation", "merge_isolation", "truncate_isolation", "rollback_retry",
        "concurrent_first_write", "compatibility", "real_tests", "scope_quality", "validation_review",
    )}
    server_bad = judge("server-hstore-graph-isolation", {
        "case_id": "server-hstore-graph-isolation",
        "trusted_oracle": True,
        "checks": server_checks,
        "facts": {"mock_only": True},
        "claims": {"complete": True},
    }, root)
    assert server_bad["score"] == 0 and server_bad["pre_critical_score"] <= 80
    assert "complete_rest_claim_without_l1" in server_bad["critical_failures"]
    assert "mock_only" in server_bad["critical_failures"]

    docs_bad = judge("docs-graphs-api-version-truth", {
        "case_id": "docs-graphs-api-version-truth",
        "trusted_oracle": True,
        "checks": {name: True for name in ("version_truth", "api_behavior", "executable_flows", "site_quality", "primary_evidence_scope")},
        "facts": {"one_language_only": True, "invented_released_1_8": True},
        "claims": {"complete": True},
    }, root)
    assert docs_bad["score"] <= 50 and docs_bad["completed"] is False

    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["pair_count"] == 3
    assert set(summary["cases"]) == set(CASE_IDS)
    assert all(item["delta_b_minus_a"] == 0 for item in summary["pairs"])
    assert "do not claim" in summary["interpretation"]

    failure_summary = json.loads((root / "failure-summary.json").read_text(encoding="utf-8"))
    assert failure_summary["pair_count"] == 1
    assert failure_summary["blinded"] is True
    assert "without_skill" not in json.dumps(failure_summary)
    failure_arms = failure_summary["pairs"][0]["arms"]
    assert len(failure_arms) == 2
    assert all(
        arm["failure_kind"] == "executor_error"
        and arm["status"] == "MODEL_FAILURE"
        and arm["scored"] is True
        for arm in failure_arms
    )

    env_summary = json.loads((root / "env-summary.json").read_text(encoding="utf-8"))
    assert all(
        arm["status"] == "ENVIRONMENT_ERROR" and arm["scored"] is False
        for arm in env_summary["pairs"][0]["arms"]
    )

    partial_pair = root / "partial-root" / "pairs" / "toolchain-empty-graph-edit" / "partial-01"
    partial_mapping = json.loads((partial_pair / "private" / "mapping.json").read_text(encoding="utf-8"))
    partial_arm = partial_mapping["roles"]["without_skill"]
    partial_execution = partial_pair / "arms" / partial_arm / "execution"
    partial_run = json.loads((partial_execution / "artifacts" / "run.json").read_text(encoding="utf-8"))
    assert partial_run["status"] == "ENVIRONMENT_ERROR"
    assert partial_run["failure_kind"] == "prompt_environment_error"
    assert not (partial_execution / "artifacts/score.json").exists()
    assert not (partial_execution / "workspace" / "fake-forwarded-goal.txt").exists()

    quality_pair = root / "quality-root" / "pairs" / "toolchain-empty-graph-edit" / "quality-fail-01"
    quality_mapping = json.loads((quality_pair / "private/mapping.json").read_text(encoding="utf-8"))
    quality_arm = quality_mapping["roles"]["without_skill"]
    quality_execution = quality_pair / "arms" / quality_arm / "execution"
    quality_run = json.loads((quality_execution / "artifacts/run.json").read_text(encoding="utf-8"))
    assert quality_run["status"] == "PASS"
    assert (quality_execution / "workspace/fake-forwarded-goal.txt").is_file()

    unknown_path = root / "unknown-fact.json"
    unknown_path.write_text(json.dumps({
        "case_id": "server-hstore-graph-isolation",
        "trusted_oracle": True,
        "checks": {},
        "facts": {"cross_graph_leek": True},
        "claims": {},
    }), encoding="utf-8")
    unknown = subprocess.run([
        sys.executable, str(SCRIPT_DIR / "judge-run.py"),
        "--case", "server-hstore-graph-isolation", "--evidence", str(unknown_path),
    ], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert unknown.returncode != 0 and b"unknown fact keys" in unknown.stderr

    judge_spec = importlib.util.spec_from_file_location("hugegraph_ab_judge_test", SCRIPT_DIR / "judge-run.py")
    assert judge_spec and judge_spec.loader
    judge_module = importlib.util.module_from_spec(judge_spec)
    judge_spec.loader.exec_module(judge_module)
    oracle_specs = {
        "toolchain-empty-graph-edit": ("HG_AB_TOOLCHAIN_ORACLE_SPEC", SUITE_DIR / "oracles" / "toolchain.sh"),
        "server-hstore-graph-isolation": ("HG_AB_SERVER_ORACLE_SPEC", SUITE_DIR / "oracles" / "server.sh"),
        "docs-graphs-api-version-truth": ("HG_AB_DOCS_ORACLE_SPEC", SUITE_DIR / "oracles" / "docs.sh"),
    }
    for case_id, (env_name, oracle) in oracle_specs.items():
        spec_path = root / f"{case_id}-oracle-spec.json"
        output_path = root / f"{case_id}-oracle-output.json"
        spec_path.write_text(json.dumps({
            "schema_version": 1,
            "case_id": case_id,
            "default_timeout_seconds": 10,
            "checks": {name: {"argv": ["/usr/bin/true"]} for name in judge_module.RULES[case_id]},
            "facts": {name: {"argv": ["/usr/bin/false"]} for name in judge_module.FACTS[case_id]},
            "claims": {"complete": {"argv": ["/usr/bin/true"]}},
        }), encoding="utf-8")
        env = os.environ.copy()
        env[env_name] = str(spec_path)
        subprocess.run([
            str(oracle), str(root / "source"), str(root / "source"), str(output_path),
        ], check=True, env=env)
        oracle_output = json.loads(output_path.read_text(encoding="utf-8"))
        assert oracle_output["trusted_oracle"] is True
        assert all(oracle_output["checks"].values()) and not any(oracle_output["facts"].values())
        assert oracle_output["claims"] == {"complete": True}

    claim_artifacts = root / "claim-agent-artifacts"
    claim_artifacts.mkdir()
    (claim_artifacts / "final.txt").write_text("COMPLETE\n", encoding="utf-8")
    claim_stdout = root / "claim-executor-stdout.txt"
    claim_stdout.write_text("DONE\n", encoding="utf-8")
    claim_spec = root / "claim-input-oracle-spec.json"
    claim_output = root / "claim-input-oracle-output.json"
    claim_case = "toolchain-empty-graph-edit"
    claim_spec.write_text(json.dumps({
        "schema_version": 1, "case_id": claim_case, "default_timeout_seconds": 10,
        "checks": {name: {"argv": ["/usr/bin/true"]} for name in judge_module.RULES[claim_case]},
        "facts": {name: {"argv": ["/usr/bin/false"]} for name in judge_module.FACTS[claim_case]},
        "claims": {"complete": {"argv": [
            sys.executable, "-c",
            "import pathlib,sys; raise SystemExit(0 if pathlib.Path(sys.argv[1],'final.txt').read_text().strip()=='COMPLETE' and pathlib.Path(sys.argv[2]).read_text().strip()=='DONE' else 1)",
            "{agent_artifacts}", "{executor_stdout}",
        ]}},
    }), encoding="utf-8")
    claim_command = [
        sys.executable, str(SCRIPT_DIR / "trusted-command-oracle.py"),
        "--case", claim_case, "--spec", str(claim_spec),
        "--workspace", str(root / "source"), "--pristine", str(root / "source"),
        "--agent-artifacts", str(claim_artifacts), "--executor-stdout", str(claim_stdout),
        "--probe-uid", str(os.getuid()), "--probe-gid", str(os.getgid()),
        "--output", str(claim_output),
    ]
    subprocess.run(claim_command, check=True)
    assert json.loads(claim_output.read_text(encoding="utf-8"))["claims"] == {"complete": True}
    missing_claim = subprocess.run(
        [item if item != str(claim_stdout) else str(root / "missing-stdout.txt") for item in claim_command],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert missing_claim.returncode != 0 and b"missing" in missing_claim.stderr

    active = json.loads((root / "preflight-active" / "metadata.json").read_text(encoding="utf-8"))
    stale = json.loads((root / "preflight-stale" / "metadata.json").read_text(encoding="utf-8"))
    drift = json.loads((root / "preflight-drift" / "metadata.json").read_text(encoding="utf-8"))
    assert active["status"] == "active"
    assert stale["status"] == "stale"
    assert drift["status"] == "needs_probe" and drift["version_drift"] is True
    assert "unexpected_official_1_8_ref" in drift["version_drift_reasons"]
    assert "resolved_working_commit" in active
    evidence_text = (root / "preflight-active" / "version-evidence" / "version-evidence.md").read_text(encoding="utf-8")
    assert "Scoped API/source evidence" in evidence_text
    for expected_path in (
        "QueryResult/Home/index.js",
        "GraphMenubar/index.js",
        "EditElement/index.js",
    ):
        assert expected_path in evidence_text
    assert "No matching source file" not in evidence_text
    assert not re.search(r"[0-9a-f]{40}", evidence_text)
    docs_evidence = (root / "preflight-docs" / "version-evidence" / "version-evidence.md").read_text(encoding="utf-8")
    assert "HugeGraphAuthProxy.java" in docs_evidence
    assert "anonymous" in docs_evidence and "getContext" in docs_evidence and "username" in docs_evidence
    docs_metadata = json.loads((root / "preflight-docs" / "metadata.json").read_text(encoding="utf-8"))
    assert docs_metadata["matching_server"]["canonical"] == "apache/hugegraph"
    assert set(docs_metadata["matching_server"]["resolved_refs"]) == {"1.5.0", "1.7.0", "master"}

    service_helper = root / "fake-service-helper.py"
    service_helper.write_text(
        """#!/usr/bin/env python3
import json, pathlib, sys
action, case_id, run_id, data_dir, output, identity = sys.argv[1:]
if action == "prepare":
    pathlib.Path(output).write_text(json.dumps({
        "schema_version": 1, "case_id": case_id, "run_id": run_id,
        "fresh_state": True, "exclusive_data_root": True,
        "data_root": str(pathlib.Path(data_dir).resolve()),
        "service_config_identity": identity,
        "network": "network-" + run_id,
        "network_id": "sha256:fake-service-network",
        "private_health_urls": ["http://hugegraph:8080/health"],
        "model_base_url": "http://model:9000/v1",
        "model_policy_url": "http://model:9000/policy",
        "model_policy_identity": "provider-only-policy-v1",
        "allowed_model": "fake",
        "provider_origin_sha256": "c" * 64,
        "service_image_ids": {"hugegraph": "sha256:hugegraph-test", "model": "sha256:model-test"},
        "service_artifact_ids": {
            "controller_sha256": "a" * 64,
            "model_proxy_sha256": "b" * 64,
        },
    }))
else:
    pathlib.Path(output + ".cleaned").write_text("cleaned")
""",
        encoding="utf-8",
    )
    service_helper.chmod(0o755)
    service_spec = root / "fake-service-spec.json"
    service_spec.write_text(json.dumps({
        "schema_version": 1,
        "case_id": "toolchain-empty-graph-edit",
        "service_config_identity": "fake-service-v1",
        "prepare_argv": [
            sys.executable, str(service_helper), "prepare", "{case}", "{run_id}",
            "{data_dir}", "{output}", "{service_config_identity}",
        ],
        "reset_argv": [
            sys.executable, str(service_helper), "prepare", "{case}", "{run_id}",
            "{data_dir}", "{output}", "{service_config_identity}",
        ],
        "cleanup_argv": [
            sys.executable, str(service_helper), "cleanup", "{case}", "{run_id}",
            "{data_dir}", "{output}", "{service_config_identity}",
        ],
        "timeout_seconds": 10,
    }), encoding="utf-8")
    service_data = root / "fake-service-data"
    service_output = root / "fake-service-attestation.json"
    for action in ("prepare", "cleanup"):
        subprocess.run([
            str(SCRIPT_DIR / "service-harness.py"), action,
            "--spec", str(service_spec), "--case", "toolchain-empty-graph-edit",
            "--run-id", "arm-123456789abc", "--data-dir", str(service_data),
            "--output", str(service_output),
        ], check=True)
    used_networks: set[str] = set()
    suite.validate_service_attestation(
        service_output, "toolchain-empty-graph-edit", "arm-123456789abc",
        service_data, "fake-service-v1", "fake", used_networks,
    )
    try:
        suite.validate_service_attestation(
            service_output, "toolchain-empty-graph-edit", "arm-123456789abc",
            service_data, "fake-service-v1", "fake", used_networks,
        )
    except suite.SuiteError as exc:
        assert "reused" in str(exc)
    else:
        raise AssertionError("service attestation accepted a reused network")

    server_pair = root / "pairs" / "server-hstore-graph-isolation" / "fake-01"
    server_mapping = json.loads((server_pair / "private" / "mapping.json").read_text(encoding="utf-8"))
    treatment_artifacts = server_pair / "arms" / server_mapping["roles"]["with_skill"] / "execution" / "artifacts"
    critical_evidence = treatment_artifacts / "behavior-evidence.json"
    critical_evidence.write_text(json.dumps({
        "case_id": "server-hstore-graph-isolation",
        "trusted_oracle": True,
        "checks": {name: True for name in judge_module.RULES["server-hstore-graph-isolation"]},
        "facts": {"cross_graph_leak": True},
        "claims": {"complete": True},
    }), encoding="utf-8")
    subprocess.run([
        sys.executable, str(SCRIPT_DIR / "judge-run.py"),
        "--case", "server-hstore-graph-isolation", "--evidence", str(critical_evidence),
        "--output", str(treatment_artifacts / "score.json"),
    ], check=True)
    treatment_run = json.loads((treatment_artifacts / "run.json").read_text(encoding="utf-8"))
    treatment_arm = server_mapping["roles"]["with_skill"]
    critical_binding = suite.bind_score(
        treatment_artifacts / "score.json",
        json.loads((server_pair / "manifest.json").read_text(encoding="utf-8")),
        treatment_arm,
        treatment_run["prompt_metrics"],
        treatment_run["execution_policy"],
        "behavior_oracle",
    )
    treatment_run["run_binding"] = critical_binding
    (treatment_artifacts / "run.json").write_text(
        json.dumps(treatment_run, indent=2) + "\n", encoding="utf-8",
    )
    critical_summary_path = root / "critical-summary.json"
    subprocess.run([
        sys.executable, str(SCRIPT_DIR / "summarize-pairs.py"),
        "--cohort", "deterministic",
        "--pair-root", str(root / "pairs" / "toolchain-empty-graph-edit" / "fake-01"),
        "--pair-root", str(server_pair),
        "--pair-root", str(root / "pairs" / "docs-graphs-api-version-truth" / "fake-01"),
        "--output", str(critical_summary_path),
    ], check=True)
    critical_summary = json.loads(critical_summary_path.read_text(encoding="utf-8"))
    server_result = next(item for item in critical_summary["pairs"] if item["case_id"] == "server-hstore-graph-isolation")
    assert server_result["outcome"] == "critical_loss"
    assert critical_summary["weighted_scores_for_display_only"]["with_skill"] is None

    # skill-up ERROR remains an explicit unscored environment arm instead of
    # being dropped before the other role can be retained.
    first_pair = root / "pairs" / "toolchain-empty-graph-edit" / "fake-01"
    first_mapping = json.loads((first_pair / "private" / "mapping.json").read_text(encoding="utf-8"))
    runtime_base = first_pair / "private" / "skill-up-runtime"
    assert not (runtime_base / first_mapping["roles"]["without_skill"] / "root" / "SKILL.md").exists()
    assert (runtime_base / first_mapping["roles"]["with_skill"] / "root" / "SKILL.md").is_file()
    runtime_case = runtime_base / first_mapping["roles"]["with_skill"] / "root/evals/cases/toolchain-empty-graph-edit.yaml"
    assert "repo_fixture: evals/fixtures/repos/source" in runtime_case.read_text(encoding="utf-8")
    assert (runtime_base / first_mapping["roles"]["with_skill"] / "root/evals/fixtures/repos/source/pom.xml").is_file()
    failed_role = "without_skill"
    failed_arm = first_mapping["roles"][failed_role]
    synthetic_result = root / "synthetic-failed-result.json"
    synthetic_result.write_text(json.dumps({
        "case_results": [{
            "case_id": "toolchain-empty-graph-edit",
            "configuration": "with_skill",
            "prompt": suite.extract_prompt(SUITE_DIR / "cases" / "toolchain-empty-graph-edit.yaml").decode(),
            "response": "",
            "status": "ERROR",
        }],
    }), encoding="utf-8")
    suite.import_skill_up_result(first_pair, synthetic_result, failed_role, {
        "model": "fake", "reasoning_effort": "fake", "timeout_seconds": 1,
        "max_turns": 1, "max_retries": 0, "skill_up_version": "synthetic",
        "runtime": "opensandbox", "sandbox_template": "synthetic",
    }, 1)
    failed_metrics = json.loads((first_pair / "arms" / failed_arm / "prompt" / "metrics.json").read_text(encoding="utf-8"))
    assert failed_metrics["failure_kind"] == "prompt_runtime_error"
    assert failed_metrics["failure_class"] == "environment"
    assert not (first_pair / "arms" / failed_arm / "prompt" / "response.txt").exists()

    # A transient real-cohort ledger must enumerate the exact pair set.  This
    # synthetic cohort exercises ledger binding, trusted score/run binding,
    # unique runtime networks, and the cross-case Pilot 2/1 order rule without
    # making model or Docker calls.
    pilot_id = "pilot-synthetic"
    pilot_roots: list[Path] = []
    ledger_entries: list[dict[str, Any]] = []
    first_schedule = ("without_skill", "with_skill", "without_skill")
    network_index = 0
    for case_index, case_id in enumerate(CASE_IDS):
        source_pair = root / "pairs" / case_id / "fake-01"
        pair_id = f"pilot-{case_index + 1}"
        pair = root / "pilot-pairs" / case_id / pair_id
        shutil.copytree(source_pair, pair)
        manifest = json.loads((pair / "manifest.json").read_text(encoding="utf-8"))
        mapping = json.loads((pair / "private" / "mapping.json").read_text(encoding="utf-8"))
        manifest.update({
            "pair_id": pair_id,
            "cohort": "pilot",
            "cohort_id": pilot_id,
            "repeat": 1,
            "preflight_status": "active",
            "preflight_refresh_mode": "online",
        })
        mapping.update({"pair_id": pair_id, "cohort": "pilot", "cohort_id": pilot_id, "repeat": 1})
        (pair / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (pair / "private" / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
        first = first_schedule[case_index]
        second = "with_skill" if first == "without_skill" else "without_skill"
        for order_name in ("prompt-order.json", "execution-order.json"):
            order_path = pair / "private" / order_name
            order_doc = json.loads(order_path.read_text(encoding="utf-8"))
            order_doc["order"] = [mapping["roles"][first], mapping["roles"][second]]
            order_path.write_text(json.dumps(order_doc, indent=2) + "\n", encoding="utf-8")
        for arm_id in mapping["roles"].values():
            network_index += 1
            artifacts = pair / "arms" / arm_id / "execution" / "artifacts"
            run = json.loads((artifacts / "run.json").read_text(encoding="utf-8"))
            score = json.loads((artifacts / "score.json").read_text(encoding="utf-8"))
            run.update({"case_id": case_id, "anonymous_run_id": arm_id, "fake": False, "status": "PASS"})
            run.pop("failure_kind", None)
            run["isolation_attestation"] = {
                "container_image_id": "sha256:executor-image",
                "oracle_image_id": "sha256:oracle-image",
                "model_policy_identity": "provider-only-policy-v1",
                "model_base_url": "http://model:9000/v1",
                "private_network_id": f"network-{network_index}",
                "service_image_ids": {"fixture": f"sha256:{case_id}-service-test"},
            }
            score.update({
                "case_id": case_id,
                "anonymous_run_id": arm_id,
                "pair_id": pair_id,
                "cohort": "pilot",
                "cohort_id": pilot_id,
                "repeat": 1,
            })
            evidence_sha256 = suite.file_digest(artifacts / "behavior-evidence.json")
            score["behavior_evidence_sha256"] = evidence_sha256
            binding = suite.run_binding(
                manifest, arm_id, run["prompt_metrics"], run["execution_policy"], evidence_sha256,
            )
            run["run_binding"] = binding
            score["run_binding"] = binding
            (artifacts / "run.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
            (artifacts / "score.json").write_text(json.dumps(score, indent=2) + "\n", encoding="utf-8")
        pilot_roots.append(pair)
        ledger_entries.append({
            "case_id": case_id, "pair_id": pair_id, "repeat": 1,
            "pair_root": str(pair), "status": "registered",
            "prompt_status": "terminal", "execution_status": "terminal",
            "terminal_arms": {str(arm_id): "PASS" for arm_id in mapping["roles"].values()},
            "planned_prompt_order": "ab" if first == "without_skill" else "ba",
            "planned_execution_order": "ab" if first == "without_skill" else "ba",
        })
    ledger_path = root / "cohorts" / pilot_id / "ledger.json"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text(json.dumps({
        "schema_version": 1, "cohort": "pilot", "cohort_id": pilot_id,
        "sealed": True,
        "pairs": ledger_entries,
    }, indent=2) + "\n", encoding="utf-8")
    pilot_summary = root / "pilot-summary.json"
    pilot_command = [
        sys.executable, str(SCRIPT_DIR / "summarize-pairs.py"),
        "--cohort", "pilot", "--cohort-id", pilot_id,
        "--ledger", str(ledger_path),
    ]
    for pair in pilot_roots:
        pilot_command.extend(("--pair-root", str(pair)))
    subprocess.run(pilot_command + ["--output", str(pilot_summary)], check=True)
    assert json.loads(pilot_summary.read_text(encoding="utf-8"))["pair_count"] == 3
    omitted = subprocess.run(
        pilot_command[:-2] + ["--output", str(root / "omitted-summary.json")],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert omitted.returncode != 0 and b"exactly match" in omitted.stderr
    for pair in pilot_roots:
        mapping = json.loads((pair / "private" / "mapping.json").read_text(encoding="utf-8"))
        path = pair / "private" / "prompt-order.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["order"] = [mapping["roles"]["without_skill"], mapping["roles"]["with_skill"]]
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    unbalanced = subprocess.run(
        pilot_command + ["--output", str(root / "unbalanced-summary.json")],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert unbalanced.returncode != 0 and (
        b"not 2/1 balanced" in unbalanced.stderr or b"differs from sealed ledger" in unbalanced.stderr
    )

    # Formal accepts per-pair moving-ref snapshots while keeping each pair's
    # two arms bound and holding oracle/service policy fixed within a case.
    formal_id = "formal-synthetic"
    formal_roots: list[Path] = []
    formal_entries: list[dict[str, Any]] = []
    formal_network = 0
    formal_orders = ("ab", "ba", "ab")
    for case_id in CASE_IDS:
        source_pair = root / "pairs" / case_id / "fake-01"
        for repeat, planned_order in enumerate(formal_orders, start=1):
            pair_id = f"formal-{repeat}"
            pair = root / "formal-pairs" / case_id / pair_id
            shutil.copytree(source_pair, pair)
            manifest = json.loads((pair / "manifest.json").read_text(encoding="utf-8"))
            mapping = json.loads((pair / "private/mapping.json").read_text(encoding="utf-8"))
            manifest.update({
                "pair_id": pair_id, "cohort": "formal", "cohort_id": formal_id,
                "repeat": repeat, "preflight_status": "active", "preflight_refresh_mode": "online",
                "source_sha256": suite.digest_bytes(f"{case_id}-source-{repeat}".encode()),
                "version_evidence_sha256": suite.digest_bytes(f"{case_id}-evidence-{repeat}".encode()),
            })
            mapping.update({"pair_id": pair_id, "cohort": "formal", "cohort_id": formal_id, "repeat": repeat})
            (pair / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            (pair / "private/mapping.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
            first = "without_skill" if planned_order == "ab" else "with_skill"
            second = "with_skill" if first == "without_skill" else "without_skill"
            for order_name in ("prompt-order.json", "execution-order.json"):
                order_path = pair / "private" / order_name
                order_doc = json.loads(order_path.read_text(encoding="utf-8"))
                order_doc["order"] = [mapping["roles"][first], mapping["roles"][second]]
                order_path.write_text(json.dumps(order_doc, indent=2) + "\n", encoding="utf-8")
            for arm_id in mapping["roles"].values():
                formal_network += 1
                artifacts = pair / "arms" / arm_id / "execution/artifacts"
                run = json.loads((artifacts / "run.json").read_text(encoding="utf-8"))
                score = json.loads((artifacts / "score.json").read_text(encoding="utf-8"))
                run.update({"case_id": case_id, "anonymous_run_id": arm_id, "fake": False, "status": "PASS"})
                run.pop("failure_kind", None)
                run["source_before_sha256"] = manifest["source_sha256"]
                run["isolation_attestation"] = {
                    "container_image_id": "sha256:executor-image",
                    "oracle_image_id": "sha256:oracle-image",
                    "model_policy_identity": "provider-only-policy-v1",
                    "model_base_url": "http://model:9000/v1",
                    "private_network_id": f"formal-network-{formal_network}",
                    "service_image_ids": {"fixture": f"sha256:{case_id}-service-test"},
                }
                score.update({
                    "case_id": case_id, "anonymous_run_id": arm_id, "pair_id": pair_id,
                    "cohort": "formal", "cohort_id": formal_id, "repeat": repeat,
                })
                evidence_sha256 = suite.file_digest(artifacts / "behavior-evidence.json")
                score["behavior_evidence_sha256"] = evidence_sha256
                binding = suite.run_binding(
                    manifest, arm_id, run["prompt_metrics"], run["execution_policy"], evidence_sha256,
                )
                run["run_binding"] = binding
                score["run_binding"] = binding
                (artifacts / "run.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
                (artifacts / "score.json").write_text(json.dumps(score, indent=2) + "\n", encoding="utf-8")
            formal_roots.append(pair)
            formal_entries.append({
                "case_id": case_id, "pair_id": pair_id, "repeat": repeat,
                "pair_root": str(pair), "status": "registered",
                "prompt_status": "terminal", "execution_status": "terminal",
                "terminal_arms": {str(arm_id): "PASS" for arm_id in mapping["roles"].values()},
                "planned_prompt_order": planned_order, "planned_execution_order": planned_order,
            })
    formal_ledger = root / "cohorts" / formal_id / "ledger.json"
    formal_ledger.parent.mkdir(parents=True, exist_ok=True)
    formal_ledger.write_text(json.dumps({
        "schema_version": 1, "cohort": "formal", "cohort_id": formal_id,
        "sealed": True, "pairs": formal_entries,
    }, indent=2) + "\n", encoding="utf-8")
    formal_summary = root / "formal-summary.json"
    formal_command = [
        sys.executable, str(SCRIPT_DIR / "summarize-pairs.py"),
        "--cohort", "formal", "--cohort-id", formal_id, "--ledger", str(formal_ledger),
    ]
    for pair in formal_roots:
        formal_command.extend(("--pair-root", str(pair)))
    subprocess.run(formal_command + ["--output", str(formal_summary)], check=True)
    formal_result = json.loads(formal_summary.read_text(encoding="utf-8"))
    assert formal_result["pair_count"] == 9
    for case_id in CASE_IDS:
        snapshots = [
            item["fixture_snapshot"]["version_evidence_sha256"]
            for item in formal_result["pairs"] if item["case_id"] == case_id
        ]
        assert len(set(snapshots)) == 3

    print("hugegraph-ab deterministic suite: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
