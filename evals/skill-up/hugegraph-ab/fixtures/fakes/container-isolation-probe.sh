#!/bin/sh
set -eu

goal="$1"
workspace="$2"
artifacts="$3"

test -r "$goal"
test -d "$workspace"
test -d "$artifacts"
test ! -e /private/mapping.json
test ! -e /ab/private/mapping.json
test ! -e /ab/arms
test ! -e /repo

if printf 'forbidden\n' >>"$workspace/version-evidence/version-evidence.md" 2>/dev/null; then
  echo "version evidence was writable" >&2
  exit 1
fi

printf 'workspace write allowed\n' >"$workspace/container-isolation-probe.txt"

# The internal service must remain reachable while a public address must not.
timeout 5 bash -c 'exec 3<>/dev/tcp/hg-ab-test-service/6333'
if timeout 3 bash -c 'exec 3<>/dev/tcp/1.1.1.1/443' 2>/dev/null; then
  echo "public egress unexpectedly succeeded" >&2
  exit 1
fi

# A background process must die with the disposable container namespace.
sleep 30 &
printf 'container isolation probe complete\n'
