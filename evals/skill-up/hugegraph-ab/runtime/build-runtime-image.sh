#!/usr/bin/env bash
set -euo pipefail

runtime_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$runtime_dir/../../../.." && pwd)"
preflight_root="${HG_AB_PREFLIGHT_ROOT:-$repo_root/.eval-work/hugegraph-ab/runs/pilot-20260820/preflight}"
executor_image="${HG_AB_EXECUTOR_IMAGE:-hg-ab-executor:pilot-20260820}"
oracle_image="${HG_AB_ORACLE_IMAGE:-hg-ab-oracle:pilot-20260820}"
context="$(mktemp -d "$repo_root/.eval-work/hg-ab-image-context.XXXXXX")"

cleanup() {
  rm -rf "$context"
}
trap cleanup EXIT

[[ -d "$preflight_root/server/source" \
   && -d "$preflight_root/toolchain/source" \
   && -d "$preflight_root/docs/source" ]] || {
  echo "the exact active preflight sources are required" >&2
  exit 1
}
source_provenance="$(python3 -c '
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
items = []
for case in ("server", "toolchain", "docs"):
    case_root = root / case
    metadata = json.loads((case_root / "metadata.json").read_text())
    h = hashlib.sha256()
    source = case_root / "source"
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise SystemExit(f"symlink is not allowed: {path}")
        if path.is_file():
            h.update(path.relative_to(source).as_posix().encode() + b"\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    h.update(chunk)
            h.update(b"\0")
    actual = h.hexdigest()
    if actual != metadata.get("source_sha256"):
        raise SystemExit(f"{case} source digest does not match active preflight metadata")
    items.append(f"{case}:{metadata.get('"'"'resolved_working_commit'"'"')}:{actual}")
print(";".join(items))
' "$preflight_root")"
runtime_bundle_sha256="$(python3 -c '
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1])
selected = [root / "Dockerfile.executor-oracle", root / "codex-executor.sh",
            root / "model-proxy.py", root / "service-controller.py", root / "trusted"]
files = []
for item in selected:
    files.extend(p for p in item.rglob("*") if p.is_file()) if item.is_dir() else files.append(item)
h = hashlib.sha256()
for path in sorted(files):
    if path.is_symlink(): raise SystemExit(f"runtime symlink is forbidden: {path}")
    h.update(path.relative_to(root).as_posix().encode() + b"\0")
    h.update(path.read_bytes()); h.update(b"\0")
print(h.hexdigest())
' "$runtime_dir")"
cp -R "$preflight_root/server/source" "$context/hugegraph"
cp -R "$preflight_root/toolchain/source" "$context/hugegraph-toolchain"
cp -R "$preflight_root/docs/source" "$context/hugegraph-doc"
mkdir -p "$context/hg-ab-runtime"
cp -R "$runtime_dir/trusted" "$context/hg-ab-runtime/trusted"
cp "$runtime_dir/codex-executor.sh" "$context/hg-ab-runtime/codex-executor.sh"

docker build \
  --file "$runtime_dir/Dockerfile.executor-oracle" \
  --target executor \
  --build-arg "HG_AB_SOURCE_PROVENANCE=$source_provenance" \
  --build-arg "HG_AB_RUNTIME_BUNDLE_SHA256=$runtime_bundle_sha256" \
  --tag "$executor_image" \
  "$context"
docker build \
  --file "$runtime_dir/Dockerfile.executor-oracle" \
  --target oracle \
  --build-arg "HG_AB_SOURCE_PROVENANCE=$source_provenance" \
  --build-arg "HG_AB_RUNTIME_BUNDLE_SHA256=$runtime_bundle_sha256" \
  --tag "$oracle_image" \
  "$context"

docker image inspect --format 'executor {{.Id}}' "$executor_image"
docker image inspect --format 'oracle {{.Id}}' "$oracle_image"
