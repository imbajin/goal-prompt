#!/usr/bin/env python3
"""Fail-closed cohort summary for anonymous HugeGraph A/B pairs."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SUITE_DIR = SCRIPT_DIR.parent
REPO_ROOT = SUITE_DIR.parents[2]
EVAL_WORK = (REPO_ROOT / ".eval-work").resolve()
ROLES = ("without_skill", "with_skill")
CASE_IDS = (
    "toolchain-empty-graph-edit",
    "server-hstore-graph-isolation",
    "docs-graphs-api-version-truth",
)
WEIGHTS = {
    "toolchain-empty-graph-edit": 0.35,
    "server-hstore-graph-isolation": 0.40,
    "docs-graphs-api-version-truth": 0.25,
}


def under_eval_work(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(EVAL_WORK)
    except ValueError as exc:
        raise ValueError(f"{label} must be under {EVAL_WORK}") from exc
    return resolved


def read_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object in {path}")
    return data


def write_output(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def stable_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_run_binding(manifest: dict[str, Any], arm_id: str,
                         prompt_metrics: dict[str, Any], execution_policy: dict[str, Any],
                         behavior_evidence_sha256: str) -> str:
    return stable_digest({
        "case_id": manifest["case_id"],
        "pair_id": manifest["pair_id"],
        "cohort": manifest["cohort"],
        "cohort_id": manifest.get("cohort_id"),
        "repeat": manifest["repeat"],
        "anonymous_run_id": arm_id,
        "raw_request_sha256": manifest["raw_request_sha256"],
        "source_sha256": manifest["source_sha256"],
        "version_evidence_sha256": manifest["version_evidence_sha256"],
        "goal_prompt_sha256": manifest["goal_prompt_sha256"],
        "response_sha256": prompt_metrics.get("response_sha256"),
        "behavior_evidence_sha256": behavior_evidence_sha256,
        "execution_policy": execution_policy,
    })


def validate_anonymous_score(manifest: dict[str, Any], arm_id: str,
                             run: dict[str, Any], score: dict[str, Any],
                             evidence_path: Path) -> None:
    if run.get("anonymous_run_id") != arm_id or run.get("case_id") != manifest.get("case_id"):
        raise ValueError("run identity mismatch")
    if run.get("status") not in ("PASS", "MODEL_FAILURE"):
        raise ValueError("run is not a terminal model outcome")
    expected = {
        "schema_version": 2,
        "case_id": manifest.get("case_id"),
        "anonymous_run_id": arm_id,
        "pair_id": manifest.get("pair_id"),
        "cohort": manifest.get("cohort"),
        "cohort_id": manifest.get("cohort_id"),
        "repeat": manifest.get("repeat"),
    }
    if any(score.get(key) != value for key, value in expected.items()):
        raise ValueError("score identity mismatch")
    prompt_metrics = run.get("prompt_metrics")
    execution_policy = run.get("execution_policy")
    if not isinstance(prompt_metrics, dict) or not isinstance(execution_policy, dict):
        raise ValueError("missing run policy/metrics")
    score_evidence_sha = score.get("behavior_evidence_sha256")
    if not isinstance(score_evidence_sha, str) or not score_evidence_sha:
        raise ValueError("score lacks behavior evidence identity")
    if not evidence_path.is_file() or file_digest(evidence_path) != score_evidence_sha:
        raise ValueError("score does not bind the retained behavior evidence")
    binding = expected_run_binding(manifest, arm_id, prompt_metrics, execution_policy, score_evidence_sha)
    if run.get("run_binding") != binding or score.get("run_binding") != binding:
        raise ValueError("trusted run/score binding mismatch")
    if run.get("status") == "MODEL_FAILURE" and float(score.get("score", -1)) != 0:
        raise ValueError("model failure lacks trusted zero score")


def validate_counts(cohort: str, manifests: list[dict[str, Any]]) -> None:
    counts = Counter(str(item["case_id"]) for item in manifests)
    if set(counts) != set(CASE_IDS):
        raise ValueError(f"cohort must contain all three cases exactly; got {dict(counts)}")
    expected = 1 if cohort == "pilot" else 3 if cohort == "formal" else None
    if expected is not None and any(counts[case_id] != expected for case_id in CASE_IDS):
        raise ValueError(f"{cohort} cohort requires {expected} pair(s) per case; got {dict(counts)}")
    if expected is not None:
        for case_id in CASE_IDS:
            repeats = sorted(int(item["repeat"]) for item in manifests if item["case_id"] == case_id)
            if repeats != list(range(1, expected + 1)):
                raise ValueError(f"{cohort} repeats must be 1..{expected} for {case_id}; got {repeats}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, choices=("deterministic", "pilot", "formal"))
    parser.add_argument("--cohort-id")
    parser.add_argument("--ledger")
    parser.add_argument("--pair-root", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--anonymous-diagnostics", action="store_true")
    args = parser.parse_args()
    try:
        output = under_eval_work(Path(args.output), "output")
        pair_roots = [under_eval_work(Path(value), "pair root") for value in args.pair_root]
        if len(set(pair_roots)) != len(pair_roots):
            raise ValueError("pair roots must be unique")
        ledger: dict[str, Any] | None = None
        if args.cohort in ("pilot", "formal"):
            if not args.cohort_id or not args.ledger:
                raise ValueError("real cohort summary requires --cohort-id and --ledger")
            ledger_path = under_eval_work(Path(args.ledger), "ledger")
            ledger = read_object(ledger_path)
            if (ledger.get("schema_version") != 1 or ledger.get("cohort") != args.cohort
                    or ledger.get("cohort_id") != args.cohort_id):
                raise ValueError("cohort ledger schema/identity mismatch")
            if ledger.get("sealed") is not True:
                raise ValueError("real cohort ledger must contain a sealed complete schedule")
            entries = ledger.get("pairs")
            if not isinstance(entries, list) or not entries or not all(isinstance(item, dict) for item in entries):
                raise ValueError("cohort ledger pairs are invalid")
            ledger_roots = [under_eval_work(Path(str(item.get("pair_root", ""))), "ledger pair root") for item in entries]
            if len(set(ledger_roots)) != len(ledger_roots):
                raise ValueError("cohort ledger contains duplicate pair roots")
            if set(ledger_roots) != set(pair_roots):
                raise ValueError("explicit pair roots must exactly match the preregistered cohort ledger")
        elif args.cohort_id or args.ledger:
            raise ValueError("deterministic summary does not use a real cohort ledger")

        snapshots: list[tuple[Path, dict[str, Any], list[dict[str, Any]]]] = []
        incomplete = False
        invalid_trusted_scores: list[str] = []
        for pair_root in pair_roots:
            manifest = read_object(pair_root / "manifest.json")
            if manifest.get("cohort") != args.cohort:
                raise ValueError(f"cohort mismatch in {pair_root}")
            if manifest.get("cohort_id") != args.cohort_id:
                raise ValueError(f"cohort id mismatch in {pair_root}")
            if manifest.get("case_id") not in CASE_IDS:
                raise ValueError(f"unknown case in {pair_root}")
            if ledger is not None:
                entry = next(
                    item for item in ledger["pairs"]
                    if under_eval_work(Path(str(item["pair_root"])), "ledger pair root") == pair_root
                )
                for key in ("case_id", "pair_id", "repeat"):
                    if entry.get(key) != manifest.get(key):
                        raise ValueError(f"ledger/manifest {key} mismatch: {pair_root}")
            if args.cohort in ("pilot", "formal"):
                if manifest.get("preflight_status") != "active" or manifest.get("preflight_refresh_mode") != "online":
                    raise ValueError(f"real cohort has non-active/non-online preflight: {pair_root}")
            arm_ids = manifest.get("arm_ids")
            if not isinstance(arm_ids, list) or len(arm_ids) != 2 or len(set(arm_ids)) != 2:
                raise ValueError(f"invalid anonymous arms: {pair_root}")
            anonymous: list[dict[str, Any]] = []
            for arm_id in arm_ids:
                artifacts = pair_root / "arms" / str(arm_id) / "execution" / "artifacts"
                run_path = artifacts / "run.json"
                score_path = artifacts / "score.json"
                run = read_object(run_path) if run_path.is_file() else {"status": "MISSING", "failure_kind": "missing_run"}
                scored = False
                if score_path.is_file() and run_path.is_file():
                    try:
                        validate_anonymous_score(
                            manifest, str(arm_id), run, read_object(score_path),
                            artifacts / "behavior-evidence.json",
                        )
                        scored = True
                    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                        invalid_trusted_scores.append(f"{pair_root}:{arm_id}: {exc}")
                incomplete = incomplete or not scored
                prompt_metrics = run.get("prompt_metrics") if isinstance(run.get("prompt_metrics"), dict) else {}
                anonymous.append({
                    "anonymous_run_id": arm_id,
                    "status": run.get("status", "UNKNOWN"),
                    "failure_kind": run.get("failure_kind"),
                    "prompt_status": prompt_metrics.get("status"),
                    "prompt_failure_kind": prompt_metrics.get("failure_kind"),
                    "prompt_cli_exit_code": prompt_metrics.get("cli_exit_code"),
                    "scored": scored,
                })
            if ledger is not None:
                terminal = {str(item["anonymous_run_id"]): item["status"] for item in anonymous}
                if (entry.get("prompt_status") != "terminal"
                        or entry.get("execution_status") != "terminal"
                        or entry.get("terminal_arms") != terminal):
                    raise ValueError(f"cohort ledger does not bind all terminal anonymous arms: {pair_root}")
            snapshots.append((pair_root, manifest, anonymous))

        if args.anonymous_diagnostics:
            write_output(output, {
                "schema_version": 2,
                "cohort": args.cohort,
                "cohort_id": args.cohort_id,
                "blinded": True,
                "pair_count": len(snapshots),
                "pairs": [
                    {"case_id": manifest["case_id"], "pair_id": manifest["pair_id"], "arms": anonymous}
                    for _, manifest, anonymous in snapshots
                ],
            })
            return 0
        validate_counts(args.cohort, [item[1] for item in snapshots])
        if invalid_trusted_scores:
            raise ValueError("invalid trusted score before unblinding: " + "; ".join(invalid_trusted_scores))
        if incomplete:
            raise ValueError("all anonymous arms must have score.json before mapping may be revealed; use --anonymous-diagnostics")

        pairs: list[dict[str, Any]] = []
        global_policy_fingerprints: set[str] = set()
        case_identity_fingerprints: dict[str, set[str]] = defaultdict(set)
        runtime_image_fingerprints: set[str] = set()
        case_service_image_fingerprints: dict[str, set[str]] = defaultdict(set)
        observed_oracle_image_ids: set[str] = set()
        observed_network_ids: set[str] = set()
        order_by_case: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"prompt": [], "execution": []})
        for pair_root, manifest, _ in snapshots:
            mapping = read_object(pair_root / "private" / "mapping.json")
            ledger_entry = None
            if ledger is not None:
                ledger_entry = next(
                    item for item in ledger["pairs"]
                    if under_eval_work(Path(str(item["pair_root"])), "ledger pair root") == pair_root
                )
            for key in ("case_id", "pair_id", "cohort", "cohort_id", "repeat"):
                if mapping.get(key) != manifest.get(key):
                    raise ValueError(f"mapping/manifest {key} mismatch: {pair_root}")
            role_map = mapping.get("roles")
            if not isinstance(role_map, dict) or set(role_map) != set(ROLES):
                raise ValueError(f"invalid mapping: {pair_root}")
            inverse = {str(arm): role for role, arm in role_map.items()}
            if set(inverse) != set(str(value) for value in manifest["arm_ids"]):
                raise ValueError(f"mapping/manifest arm mismatch: {pair_root}")

            prompt_order = read_object(pair_root / "private" / "prompt-order.json")
            execution_order = read_object(pair_root / "private" / "execution-order.json")
            for label, order_doc in (("prompt", prompt_order), ("execution", execution_order)):
                order = order_doc.get("order")
                if not isinstance(order, list) or set(str(item) for item in order) != set(inverse):
                    raise ValueError(f"invalid {label} order: {pair_root}")
                order_by_case[str(manifest["case_id"])][label].append(inverse[str(order[0])])
                if ledger_entry is not None:
                    actual_order = "ab" if inverse[str(order[0])] == "without_skill" else "ba"
                    if ledger_entry.get(f"planned_{label}_order") != actual_order:
                        raise ValueError(f"{label} order differs from sealed ledger: {pair_root}")

            arms: dict[str, Any] = {}
            for role in ROLES:
                arm_id = str(role_map[role])
                artifacts = pair_root / "arms" / arm_id / "execution" / "artifacts"
                run = read_object(artifacts / "run.json")
                score = read_object(artifacts / "score.json")
                if run.get("anonymous_run_id") != arm_id or run.get("case_id") != manifest["case_id"]:
                    raise ValueError(f"run identity mismatch: {artifacts}")
                if (score.get("schema_version") != 2 or score.get("case_id") != manifest["case_id"]
                        or score.get("anonymous_run_id") != arm_id
                        or score.get("pair_id") != manifest["pair_id"]
                        or score.get("cohort") != manifest["cohort"]
                        or score.get("cohort_id") != manifest.get("cohort_id")
                        or score.get("repeat") != manifest["repeat"]):
                    raise ValueError(f"score identity mismatch: {artifacts}")
                if run.get("status") not in ("PASS", "MODEL_FAILURE"):
                    raise ValueError(f"normal summary refuses a non-terminal model outcome: {artifacts}")
                expected_fake = args.cohort == "deterministic"
                if bool(run.get("fake")) != expected_fake:
                    raise ValueError(f"fake/real cohort mismatch: {artifacts}")
                prompt_metrics = run.get("prompt_metrics")
                execution_policy = run.get("execution_policy")
                if not isinstance(prompt_metrics, dict) or not isinstance(execution_policy, dict):
                    raise ValueError(f"missing policy/metrics: {artifacts}")
                evidence_path = artifacts / "behavior-evidence.json"
                evidence_sha256 = score.get("behavior_evidence_sha256")
                if (not isinstance(evidence_sha256, str) or not evidence_path.is_file()
                        or file_digest(evidence_path) != evidence_sha256):
                    raise ValueError(f"score/evidence identity mismatch: {artifacts}")
                binding = expected_run_binding(
                    manifest, arm_id, prompt_metrics, execution_policy, evidence_sha256,
                )
                if run.get("run_binding") != binding or score.get("run_binding") != binding:
                    raise ValueError(f"trusted run/score binding mismatch: {artifacts}")
                if run.get("status") == "MODEL_FAILURE" and float(score.get("score", -1)) != 0:
                    raise ValueError(f"model failure must retain a trusted zero score: {artifacts}")
                global_execution = {
                    key: execution_policy.get(key)
                    for key in (
                        "model", "reasoning_effort", "timeout_seconds", "oracle_timeout_seconds",
                        "service_timeout_seconds",
                        "max_turns", "max_retries", "isolation_wrapper_sha256", "executor_sha256",
                        "oracle_adapter_sha256", "oracle_isolation_sha256", "service_harness_sha256", "judge_sha256",
                        "trusted_command_oracle_sha256", "network_probe_sha256", "executor_image",
                        "oracle_image", "goal_prompt_sha256", "pids_limit", "memory_limit", "cpu_limit",
                        "runtime_bundle_sha256",
                    )
                }
                global_policy_fingerprints.add(json.dumps({
                    "prompt": {key: prompt_metrics.get(key) for key in (
                        "model", "reasoning_effort", "model_base_url", "model_egress_target",
                        "model_policy_url", "model_policy_identity", "timeout_seconds", "max_turns",
                        "retries", "skill_up_version", "runtime", "sandbox_template", "runtime_attestation",
                    )},
                    "execution": global_execution,
                }, sort_keys=True))
                case_identity_fingerprints[str(manifest["case_id"])].add(json.dumps({
                    "oracle_spec_sha256": execution_policy.get("oracle_spec_sha256"),
                    "service_spec_sha256": execution_policy.get("service_spec_sha256"),
                    "service_config_identity": execution_policy.get("service_config_identity"),
                }, sort_keys=True))
                isolation = run.get("isolation_attestation")
                if run.get("failure_kind") != "prompt_failure":
                    if not isinstance(isolation, dict):
                        raise ValueError(f"executed arm lacks isolation attestation: {artifacts}")
                    runtime_image_fingerprints.add(json.dumps({
                        "container_image_id": isolation.get("container_image_id"),
                        "model_policy_identity": isolation.get("model_policy_identity"),
                        "model_base_url": isolation.get("model_base_url"),
                        "image_source_provenance": isolation.get("image_source_provenance"),
                        "provider_origin_sha256": isolation.get("provider_origin_sha256"),
                    }, sort_keys=True))
                    case_service_image_fingerprints[str(manifest["case_id"])].add(
                        json.dumps({
                            "images": isolation.get("service_image_ids"),
                            "artifacts": isolation.get("service_artifact_ids"),
                            "oracle_images": isolation.get("oracle_service_image_ids"),
                            "oracle_artifacts": isolation.get("oracle_service_artifact_ids"),
                        }, sort_keys=True)
                    )
                    oracle_image_id = isolation.get("oracle_image_id")
                    if isinstance(oracle_image_id, str) and oracle_image_id:
                        observed_oracle_image_ids.add(oracle_image_id)
                    if run.get("status") == "PASS" and not expected_fake and not oracle_image_id:
                        raise ValueError(f"successful real arm lacks oracle image identity: {artifacts}")
                    network_id = isolation.get("private_network_id")
                    if not expected_fake:
                        if not isinstance(network_id, str) or not network_id or network_id in observed_network_ids:
                            raise ValueError("real anonymous arms must use unique private network IDs")
                        observed_network_ids.add(network_id)
                arms[role] = {
                    "status": run.get("status"),
                    "failure_kind": run.get("failure_kind"),
                    "score": float(score["score"]),
                    "raw_score": float(score["raw_score"]),
                    "pre_critical_score": float(score.get("pre_critical_score", score["score"])),
                    "completed": bool(score["completed"]),
                    "critical_failures": list(score.get("critical_failures", [])),
                    "prompt_score": prompt_metrics.get("prompt_score"),
                    "prompt_metrics": {key: prompt_metrics.get(key) for key in (
                        "status", "failure_kind", "cli_exit_code", "input_tokens", "output_tokens",
                        "duration_seconds", "turns", "retries",
                    )},
                    "execution_metrics": {
                        "duration_seconds": float(run.get("duration_seconds", 0)),
                        "attempts": int(run.get("attempts", 1)),
                    },
                }
            a = arms["without_skill"]
            b = arms["with_skill"]
            a_critical = bool(a["critical_failures"])
            b_critical = bool(b["critical_failures"])
            delta = b["score"] - a["score"]
            if a_critical or b_critical:
                outcome = "critical_tie" if a_critical and b_critical else "critical_loss" if b_critical else "critical_win"
            else:
                outcome = "win" if delta > 0 else "loss" if delta < 0 else "tie"
            pairs.append({
                "case_id": manifest["case_id"],
                "pair_id": manifest["pair_id"],
                "repeat": manifest["repeat"],
                "fixture_snapshot": {
                    "source_sha256": manifest.get("source_sha256"),
                    "version_evidence_sha256": manifest.get("version_evidence_sha256"),
                    "raw_request_sha256": manifest.get("raw_request_sha256"),
                    "preflight_status": manifest.get("preflight_status"),
                    "preflight_refresh_mode": manifest.get("preflight_refresh_mode"),
                },
                "without_skill": a,
                "with_skill": b,
                "delta_b_minus_a": delta,
                "outcome": outcome,
            })

        if len(global_policy_fingerprints) != 1:
            raise ValueError("model/runtime/budget policy differs across cohort arms")
        if any(len(values) != 1 for values in case_identity_fingerprints.values()):
            raise ValueError("oracle/service policy identity differs within a case")
        if len(runtime_image_fingerprints) > 1 or len(observed_oracle_image_ids) > 1:
            raise ValueError("actual executor/oracle image or model-policy identity differs across cohort arms")
        if any(len(values) != 1 for values in case_service_image_fingerprints.values()):
            raise ValueError("actual service image identities differ within a case")
        if args.cohort == "pilot":
            for stage in ("prompt", "execution"):
                first_roles = [stages[stage][0] for stages in order_by_case.values()]
                counts = Counter(first_roles)
                if set(counts) != set(ROLES) or sorted(counts.values()) != [1, 2]:
                    raise ValueError(f"pilot {stage} first-role schedule is not 2/1 balanced: {dict(counts)}")
        if args.cohort == "formal":
            for case_id, stages in order_by_case.items():
                for stage, first_roles in stages.items():
                    counts = Counter(first_roles)
                    if set(counts) != set(ROLES) or abs(counts[ROLES[0]] - counts[ROLES[1]]) > 1:
                        raise ValueError(f"formal {stage} order is not balanced for {case_id}: {dict(counts)}")

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for pair in pairs:
            grouped[str(pair["case_id"])].append(pair)
        case_summary: dict[str, Any] = {}
        for case_id, items in sorted(grouped.items()):
            deltas = [float(item["delta_b_minus_a"]) for item in items]
            role_summaries: dict[str, Any] = {}
            for role in ROLES:
                arms = [item[role] for item in items]
                role_summaries[role] = {
                    "score_mean": mean([float(arm["score"]) for arm in arms]),
                    "completion_rate": sum(bool(arm["completed"]) for arm in arms) / len(arms),
                    "critical_failure_rate": sum(bool(arm["critical_failures"]) for arm in arms) / len(arms),
                }
            case_summary[case_id] = {
                "pair_count": len(items),
                "delta_median": statistics.median(deltas),
                "wins": sum(item["outcome"] == "win" for item in items),
                "ties": sum(item["outcome"] == "tie" for item in items),
                "losses": sum(item["outcome"] == "loss" for item in items),
                "critical_wins": sum(item["outcome"] == "critical_win" for item in items),
                "critical_ties": sum(item["outcome"] == "critical_tie" for item in items),
                "critical_losses": sum(item["outcome"] == "critical_loss" for item in items),
                **role_summaries,
            }

        weighted: dict[str, float | None] = {role: None for role in ROLES}
        weighted_reason: dict[str, str | None] = {role: None for role in ROLES}
        for role in ROLES:
            if any(pair[role]["critical_failures"] for pair in pairs):
                weighted_reason[role] = "suppressed because at least one arm has a critical failure"
            else:
                weighted[role] = sum(WEIGHTS[case_id] * float(case_summary[case_id][role]["score_mean"]) for case_id in CASE_IDS)
        weighted_delta = None
        if weighted["without_skill"] is not None and weighted["with_skill"] is not None:
            weighted_delta = weighted["with_skill"] - weighted["without_skill"]
        result = {
            "schema_version": 2,
            "cohort": args.cohort,
            "cohort_id": args.cohort_id,
            "blinded": False,
            "pair_count": len(pairs),
            "pairs": pairs,
            "cases": case_summary,
            "weighted_scores_for_display_only": weighted,
            "weighted_delta_b_minus_a_for_display_only": weighted_delta,
            "weighted_suppression_reason": weighted_reason,
            "weights": WEIGHTS,
            "interpretation": "Engineering exploration only; do not claim statistical significance or Treatment superiority from suite implementation or incomplete evidence.",
        }
        write_output(output, result)
        return 0
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
