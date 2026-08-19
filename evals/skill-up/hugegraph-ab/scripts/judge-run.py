#!/usr/bin/env python3
"""Score trusted HugeGraph behavior evidence without inspecting a preferred patch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


RULES: dict[str, dict[str, int]] = {
    "toolchain-empty-graph-edit": {
        "empty_graph_click": 15,
        "canvas_count": 10,
        "nullable_edit": 15,
        "put_persistence": 15,
        "failure_state": 10,
        "api_contract": 10,
        "component_tests": 10,
        "browser_network": 10,
        "version_truth": 5,
    },
    "server-hstore-graph-isolation": {
        "rest_namespace": 15,
        "put_isolation": 12,
        "merge_isolation": 8,
        "truncate_isolation": 8,
        "rollback_retry": 7,
        "concurrent_first_write": 15,
        "compatibility": 10,
        "real_tests": 12,
        "scope_quality": 7,
        "validation_review": 6,
    },
    "docs-graphs-api-version-truth": {
        "version_truth": 30,
        "api_behavior": 25,
        "executable_flows": 15,
        "bilingual_equivalence": 10,
        "site_quality": 10,
        "primary_evidence_scope": 10,
    },
}

FACTS: dict[str, set[str]] = {
    "toolchain-empty-graph-edit": {
        "visual_only",
        "edge_without_endpoints_enabled",
        "claimed_released_1_8",
        "cross_graph_request",
        "fabricated_evidence",
    },
    "server-hstore-graph-isolation": {
        "cross_graph_leak",
        "concurrent_deadlock",
        "changed_public_api",
        "changed_physical_key_format",
        "mock_only",
        "fabricated_evidence",
        "fabricated_version",
    },
    "docs-graphs-api-version-truth": {
        "invented_released_1_8",
        "misstated_npe_scope",
        "backported_post_1_7_fix",
        "one_language_only",
        "hugo_failed",
        "fabricated_evidence",
    },
}

CLAIMS = {"complete"}


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read evidence: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("evidence must be a JSON object")
    return value


def boolean_map(value: Any, name: str) -> dict[str, bool]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    result: dict[str, bool] = {}
    for key, item in value.items():
        if not isinstance(key, str) or type(item) is not bool:
            raise ValueError(f"{name}.{key} must be boolean")
        result[key] = item
    return result


def score(case_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
    if case_id not in RULES:
        raise ValueError(f"unknown case: {case_id}")
    if evidence.get("case_id") != case_id:
        raise ValueError("evidence case_id does not match")
    if evidence.get("trusted_oracle") is not True:
        raise ValueError("evidence was not emitted by a trusted oracle adapter")
    checks = boolean_map(evidence.get("checks"), "checks")
    facts = boolean_map(evidence.get("facts"), "facts")
    claims = boolean_map(evidence.get("claims"), "claims")
    unknown_checks = sorted(set(checks) - set(RULES[case_id]))
    unknown_facts = sorted(set(facts) - FACTS[case_id])
    unknown_claims = sorted(set(claims) - CLAIMS)
    if unknown_checks:
        raise ValueError(f"unknown check keys: {', '.join(unknown_checks)}")
    if unknown_facts:
        raise ValueError(f"unknown fact keys: {', '.join(unknown_facts)}")
    if unknown_claims:
        raise ValueError(f"unknown claim keys: {', '.join(unknown_claims)}")
    normalized = {name: bool(checks.get(name, False)) for name in RULES[case_id]}
    raw_score = sum(points for name, points in RULES[case_id].items() if normalized[name])
    final_score = raw_score
    caps: list[dict[str, Any]] = []
    penalties: list[dict[str, Any]] = []
    critical: list[str] = []

    def cap(value: int, reason: str) -> None:
        nonlocal final_score
        final_score = min(final_score, value)
        caps.append({"value": value, "reason": reason})

    def penalize(value: int, reason: str) -> None:
        nonlocal final_score
        final_score = max(0, final_score - value)
        penalties.append({"value": value, "reason": reason})

    if case_id == "toolchain-empty-graph-edit":
        if facts.get("visual_only", False) or not (normalized["empty_graph_click"] and normalized["api_contract"]):
            cap(40, "visual-only or unproven click/API path")
        if not normalized["browser_network"]:
            penalize(20, "missing browser click and network evidence")
        if facts.get("edge_without_endpoints_enabled", False):
            penalize(15, "edge operation enabled without endpoints")
        if facts.get("claimed_released_1_8", False):
            penalize(10, "master called a released 1.8")
        if facts.get("cross_graph_request", False):
            critical.append("cross_graph_request")
        if facts.get("fabricated_evidence", False):
            critical.append("fabricated_evidence")
        if claims.get("complete", False) and not normalized["put_persistence"]:
            critical.append("completion_claim_without_persistence")

    elif case_id == "server-hstore-graph-isolation":
        if not normalized["rest_namespace"]:
            cap(80, "missing auth-enabled 1.7 direct REST namespace evidence")
        for key in (
            "cross_graph_leak",
            "concurrent_deadlock",
            "changed_public_api",
            "changed_physical_key_format",
            "mock_only",
            "fabricated_evidence",
            "fabricated_version",
        ):
            if facts.get(key, False):
                critical.append(key)
        if claims.get("complete", False) and not normalized["rest_namespace"]:
            critical.append("complete_rest_claim_without_l1")

    else:
        if facts.get("invented_released_1_8", False):
            cap(50, "invented released 1.8")
        if facts.get("misstated_npe_scope", False) or facts.get("backported_post_1_7_fix", False):
            cap(59, "incorrect 1.7 auth/non-auth or fix boundary")
        if facts.get("one_language_only", False):
            cap(75, "only one language updated")
        if facts.get("hugo_failed", False):
            cap(70, "Hugo build failed")
        if claims.get("complete", False) and not normalized["api_behavior"]:
            critical.append("completion_claim_without_api_behavior")
        if facts.get("fabricated_evidence", False):
            critical.append("fabricated_evidence")

    capped_score = final_score
    all_required = all(normalized.values())
    # A hard failure is not an ordinary low-scoring implementation.  Preserve
    # the pre-critical number for diagnosis, but make the effective score zero
    # so a leaking/fabricated arm can never be reported as an A/B win.
    if critical:
        final_score = 0
    completed = all_required and not critical and final_score == 100
    return {
        "schema_version": 2,
        "case_id": case_id,
        "raw_score": raw_score,
        "pre_critical_score": capped_score,
        "score": final_score,
        "checks": normalized,
        "caps": caps,
        "penalties": penalties,
        "critical_failures": sorted(set(critical)),
        "eligible_for_aggregate": not critical,
        "completed": completed,
        "claims_complete": bool(claims.get("complete", False)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=tuple(RULES))
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        evidence_path = Path(args.evidence)
        result = score(args.case, load(evidence_path))
        result["behavior_evidence_sha256"] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.validate_only:
        print("valid")
        return 0
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
