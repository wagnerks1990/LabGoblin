#!/bin/sh
# Exit nonzero when the validated documentation commit is no longer main.
set -eu
expected_sha=$1
repository=$2
current_sha=$(git ls-remote "$repository" refs/heads/main | cut -f1)
test -n "$current_sha" && test "$expected_sha" = "$current_sha"
