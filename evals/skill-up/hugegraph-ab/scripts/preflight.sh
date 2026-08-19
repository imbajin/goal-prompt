#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: preflight.sh --case CASE --repo GIT_REPO --output .eval-work/PATH
                    [--server-repo GIT_REPO] [--stale-probe EXECUTABLE]
                    [--offline]

The trusted stale probe receives the exported source directory.
Exit 0 = active, exit 10 = stale, any other exit = preflight failure.
Without a probe the status is needs_probe and real model execution is blocked.
EOF
}

case_id=""
repo=""
server_repo=""
output=""
stale_probe=""
offline=0

while (($#)); do
  case "$1" in
    --case) case_id="${2:-}"; shift 2 ;;
    --repo) repo="${2:-}"; shift 2 ;;
    --server-repo) server_repo="${2:-}"; shift 2 ;;
    --output) output="${2:-}"; shift 2 ;;
    --stale-probe) stale_probe="${2:-}"; shift 2 ;;
    --offline) offline=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

case "$case_id" in
  toolchain-empty-graph-edit)
    canonical="apache/hugegraph-toolchain"
    work_ref="master"
    evidence_refs=("1.5.0" "1.7.0" "master")
    ;;
  server-hstore-graph-isolation)
    canonical="apache/hugegraph"
    work_ref="1.7.0"
    evidence_refs=("1.5.0" "1.7.0" "master")
    ;;
  docs-graphs-api-version-truth)
    canonical="apache/hugegraph-doc"
    work_ref="master"
    evidence_refs=("release-1.5.0" "1.7.0" "master")
    ;;
  *) echo "invalid --case: $case_id" >&2; usage; exit 2 ;;
esac

[[ -n "$repo" && -n "$output" ]] || { usage; exit 2; }
repo="$(cd "$repo" && pwd)"
repo_root="$(git -C "$repo" rev-parse --show-toplevel)"
[[ "$repo" == "$repo_root" ]] || repo="$repo_root"

workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
eval_root="$workspace_root/.eval-work"
mkdir -p "$eval_root"
output_abs="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$output")"
case "$output_abs" in
  "$eval_root"/*) ;;
  *) echo "--output must be under $eval_root" >&2; exit 2 ;;
esac
[[ ! -e "$output_abs" ]] || { echo "preflight output already exists: $output_abs" >&2; exit 1; }
mkdir -p "$(dirname "$output_abs")"

normalize_remote() {
  local value="$1"
  value="${value#git@github.com:}"
  value="${value#https://github.com/}"
  value="${value#http://github.com/}"
  value="${value%.git}"
  printf '%s\n' "$value"
}

check_canonical() {
  local checkout="$1"
  local expected="$2"
  local origin
  origin="$(git -C "$checkout" remote get-url origin)"
  [[ "$(normalize_remote "$origin")" == "$expected" ]] || {
    echo "origin is not canonical $expected: $origin" >&2
    exit 1
  }
}

resolve_ref() {
  local checkout="$1"
  local ref="$2"
  local candidate
  for candidate in "refs/tags/$ref" "refs/remotes/origin/$ref" "refs/heads/$ref" "$ref"; do
    if git -C "$checkout" rev-parse --verify --quiet "$candidate^{commit}" >/dev/null; then
      git -C "$checkout" rev-parse "$candidate^{commit}"
      return 0
    fi
  done
  echo "required ref is not available locally: $ref in $checkout" >&2
  return 1
}

has_1_8_ref() {
  local checkout="$1"
  git -C "$checkout" for-each-ref --format='%(refname:short)' refs/tags refs/remotes/origin \
    | grep -Eq '(^|/)(v?1\.8([.-]|$)|release-1\.8([.-]|$))'
}

emit_named_source_matches() {
  local checkout="$1"
  local commit="$2"
  local file_pattern="$3"
  local line_pattern="$4"
  local limit="${5:-80}"
  local required="${6:-0}"
  local path
  path="$(git -C "$checkout" ls-tree -r --name-only "$commit" \
    | grep -E "$file_pattern" \
    | head -n 1 || true)"
  if [[ -z "$path" ]]; then
    echo "- No matching source file for pattern: $file_pattern"
    [[ "$required" != "1" ]]
    return
  fi
  echo "File: $path"
  local matches
  matches="$(git -C "$checkout" show "$commit:$path" \
    | grep -n -E "$line_pattern" \
    | head -n "$limit" || true)"
  printf '%s\n' "$matches"
  if [[ -z "$matches" && "$required" == "1" ]]; then
    echo "required source markers are missing: $path" >&2
    return 1
  fi
}

tree_digest() {
  python3 -c '
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
h = hashlib.sha256()
for path in sorted(root.rglob("*")):
    if path.is_symlink():
        raise SystemExit(f"symlink is not allowed in preflight output: {path}")
    if path.is_file():
        rel = path.relative_to(root).as_posix().encode()
        h.update(rel + b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        h.update(b"\0")
print(h.hexdigest())
' "$1"
}

check_canonical "$repo" "$canonical"
if [[ "$case_id" == "docs-graphs-api-version-truth" ]]; then
  [[ -n "$server_repo" ]] || { echo "docs case requires --server-repo" >&2; exit 2; }
  server_repo="$(cd "$server_repo" && git rev-parse --show-toplevel)"
  check_canonical "$server_repo" "apache/hugegraph"
fi

if ((offline == 0)); then
  git -C "$repo" fetch --prune origin \
    '+refs/heads/*:refs/remotes/origin/*' \
    '+refs/tags/*:refs/tags/*'
  if [[ -n "$server_repo" ]]; then
    git -C "$server_repo" fetch --prune origin \
      '+refs/heads/*:refs/remotes/origin/*' \
      '+refs/tags/*:refs/tags/*'
  fi
fi

refresh_mode="online"
if ((offline == 1)); then
  refresh_mode="offline"
fi

mkdir -p "$output_abs/source" "$output_abs/version-evidence"
work_commit="$(resolve_ref "$repo" "$work_ref")"
git -C "$repo" archive "$work_commit" | tar -x -C "$output_abs/source"
[[ ! -e "$output_abs/source/.git" ]] || { echo "archive unexpectedly contains .git" >&2; exit 1; }

evidence_file="$output_abs/version-evidence/version-evidence.md"
{
  echo "# Trusted version evidence"
  echo
  echo "- Case: $case_id"
  echo "- Canonical repository: $canonical"
  echo "- Working ref: $work_ref"
  echo "- Verified at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- This file contains version/API facts only. It intentionally excludes issue/PR identifiers, root cause, patches, judges, and variant labels."
  echo
  echo "## Available official refs"
  for ref in "${evidence_refs[@]}"; do
    resolve_ref "$repo" "$ref" >/dev/null
    echo "- $ref"
  done
  echo
  echo "## Version file excerpts"
} >"$evidence_file"

for ref in "${evidence_refs[@]}"; do
  {
    echo
    echo "### $ref"
    if git -C "$repo" cat-file -e "$(resolve_ref "$repo" "$ref"):pom.xml" 2>/dev/null; then
      git -C "$repo" show "$(resolve_ref "$repo" "$ref"):pom.xml" \
        | grep -E '<revision>|<version>|<hugegraph.version>' \
        | head -n 20 || true
    else
      echo "- No root pom.xml at this ref; ref presence verified."
    fi
  } >>"$evidence_file"
done


{
  echo
  echo "## Scoped API/source evidence"
  echo "The excerpts below are deliberately limited to public API, component reachability, and version behavior."
  echo "They exclude issue/PR identifiers, fix diffs, root-cause explanations, and expected patches."
} >>"$evidence_file"

for ref in "${evidence_refs[@]}"; do
  commit="$(resolve_ref "$repo" "$ref")"
  {
    echo
    echo "### Source/API markers at $ref"
    case "$case_id" in
      toolchain-empty-graph-edit)
        strict=0
        if [[ "$ref" == "master" ]]; then strict=1; fi
        emit_named_source_matches "$repo" "$commit" \
          '(^|/)(QueryResult|GraphQueryResult)(\.(tsx|ts|jsx|js)|/((GraphResult/)?Home/)?index\.(tsx|ts|jsx|js))$' \
          'GraphQueryResult|vertices|edges|graphData|count' 100 "$strict"
        emit_named_source_matches "$repo" "$commit" \
          '(^|/)GraphMenubar(\.(tsx|ts|jsx|js)|/index\.(tsx|ts|jsx|js))$' \
          'New|new|vertex|edge|disabled|menu' 100 "$strict"
        emit_named_source_matches "$repo" "$commit" \
          '(^|/)EditElement(\.(tsx|ts|jsx|js)|/index\.(tsx|ts|jsx|js))$' \
          'propert|nullable|schema|intersection|vertex' 100 "$strict"
        ;;
      server-hstore-graph-isolation)
        emit_named_source_matches "$repo" "$commit" \
          '(^|/)GraphsAPI\.java$' \
          '@Path|@POST|@GET|@DELETE|Consumes|Produces|graphspace|graphs|Status' 120
        emit_named_source_matches "$repo" "$commit" \
          '(^|/)BusinessHandler\.java$' \
          'doBatch|doGet|truncate|rollback|merge|put' 100
        ;;
      docs-graphs-api-version-truth)
        for page in \
          content/en/docs/clients/restful-api/graphs.md \
          content/cn/docs/clients/restful-api/graphs.md
        do
          if git -C "$repo" cat-file -e "$commit:$page" 2>/dev/null; then
            echo "File: $page"
            git -C "$repo" show "$commit:$page" \
              | grep -n -E 'graphspace|graphs|Content-Type|text/plain|application/json|backend|cassandra|auth|鉴权|认证|status|状态' \
              | head -n 180 || true
          fi
        done
        ;;
    esac
  } >>"$evidence_file"
done

if [[ "$case_id" == "docs-graphs-api-version-truth" ]]; then
  {
    echo
    echo "## Matching HugeGraph Server API evidence"
    echo "Only endpoint declarations and version refs are included; no fix diff or history is provided."
  } >>"$evidence_file"
  for ref in "1.5.0" "1.7.0" "master"; do
    server_commit="$(resolve_ref "$server_repo" "$ref")"
    {
      echo
      echo "### Server $ref"
      emit_named_source_matches "$server_repo" "$server_commit" \
        '(^|/)GraphsAPI\.java$' \
        '@Path|@POST|@GET|@DELETE|Consumes|Produces|graphspace|graphs|Status|creator|user\(' 180
      emit_named_source_matches "$server_repo" "$server_commit" \
        '(^|/)GraphManager\.java$' \
        'creator|user\(|auth|graphspace|createGraph' 100
      auth_strict=0
      if [[ "$ref" == "master" ]]; then auth_strict=1; fi
      emit_named_source_matches "$server_repo" "$server_commit" \
        '(^|/)HugeGraphAuthProxy\.java$' \
        'username|anonymous|getContext|user\(|auth' 160 "$auth_strict"
      emit_named_source_matches "$server_repo" "$server_commit" \
        '(^|/)BackendProviderFactory\.java$' \
        'ALLOWED_BACKENDS|backend|provider|register' 120
    } >>"$evidence_file"
  done
fi

version_drift=0
drift_reasons=()
if has_1_8_ref "$repo"; then
  version_drift=1
  drift_reasons+=("unexpected_official_1_8_ref")
fi
master_pom="$(git -C "$repo" show "$(resolve_ref "$repo" master):pom.xml" 2>/dev/null || true)"
case "$case_id" in
  toolchain-empty-graph-edit)
    grep -Eq '<revision>1\.8\.0</revision>' <<<"$master_pom" || { version_drift=1; drift_reasons+=("toolchain_master_revision_changed"); }
    grep -Eq '<hugegraph\.version>1\.7\.0</hugegraph\.version>' <<<"$master_pom" || { version_drift=1; drift_reasons+=("toolchain_hugegraph_dependency_changed"); }
    ;;
  server-hstore-graph-isolation)
    server_master_version="$(python3 -c '
import sys, xml.etree.ElementTree as ET
root = ET.fromstring(sys.stdin.read())
direct = root.find("{*}version")
revision = root.find("{*}properties/{*}revision")
print((revision.text if revision is not None else direct.text if direct is not None else "").strip())
' <<<"$master_pom" 2>/dev/null || true)"
    [[ "$server_master_version" == "1.7.0" ]] || { version_drift=1; drift_reasons+=("server_master_version_changed"); }
    ;;
  docs-graphs-api-version-truth)
    if has_1_8_ref "$server_repo"; then
      version_drift=1
      drift_reasons+=("unexpected_server_1_8_ref")
    fi
    ;;
esac

status="needs_probe"
if [[ -n "$stale_probe" ]]; then
  [[ -x "$stale_probe" ]] || { echo "stale probe is not executable: $stale_probe" >&2; exit 2; }
  set +e
  "$stale_probe" "$output_abs/source" >"$output_abs/stale-probe.log" 2>&1
  probe_status=$?
  set -e
  case "$probe_status" in
    0) status="active" ;;
    10) status="stale" ;;
    *) echo "trusted stale probe failed with exit $probe_status" >&2; exit 1 ;;
  esac
fi

if ((version_drift == 1)) && [[ "$status" == "active" ]]; then
  status="needs_probe"
fi

source_sha256="$(tree_digest "$output_abs/source")"
evidence_sha256="$(tree_digest "$output_abs/version-evidence")"
drift_text="$(printf '%s\n' "${drift_reasons[@]:-}")"

refs_json="$(for ref in "${evidence_refs[@]}"; do printf '%s\t%s\n' "$ref" "$(resolve_ref "$repo" "$ref")"; done)"
server_refs_json=""
if [[ -n "$server_repo" ]]; then
  server_refs_json="$(for ref in "1.5.0" "1.7.0" "master"; do printf '%s\t%s\n' "$ref" "$(resolve_ref "$server_repo" "$ref")"; done)"
fi
python3 -c '
import json, sys
case_id, canonical, work_ref, work_commit, status, refs_text, server_refs_text, refresh_mode, source_sha256, evidence_sha256, drift_text, output = sys.argv[1:]
refs = dict(line.split("\t", 1) for line in refs_text.splitlines())
server_refs = dict(line.split("\t", 1) for line in server_refs_text.splitlines()) if server_refs_text else None
drift_reasons = [line for line in drift_text.splitlines() if line]
with open(output, "w", encoding="utf-8") as handle:
    json.dump({
        "schema_version": 2,
        "case_id": case_id,
        "canonical": canonical,
        "working_ref": work_ref,
        "resolved_working_commit": work_commit,
        "resolved_refs": refs,
        "matching_server": {"canonical": "apache/hugegraph", "resolved_refs": server_refs} if server_refs is not None else None,
        "status": status,
        "refresh_mode": refresh_mode,
        "source_sha256": source_sha256,
        "version_evidence_sha256": evidence_sha256,
        "version_drift": bool(drift_reasons),
        "version_drift_reasons": drift_reasons,
    }, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
' "$case_id" "$canonical" "$work_ref" "$work_commit" "$status" "$refs_json" "$server_refs_json" "$refresh_mode" "$source_sha256" "$evidence_sha256" "$drift_text" "$output_abs/metadata.json"

chmod -R a-w "$output_abs/version-evidence"
printf '%s\n' "$output_abs"
