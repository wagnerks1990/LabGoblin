#!/bin/sh
# Return 0=current, 1=superseded, 2=transport/authentication/missing-ref error.
set -eu
expected_sha=$1
repository=$2
references=$(git ls-remote "$repository" refs/heads/main) || exit 2
current_sha=$(printf '%s\n' "$references" | cut -f1)
test -n "$current_sha" || exit 2
test "$expected_sha" = "$current_sha"
