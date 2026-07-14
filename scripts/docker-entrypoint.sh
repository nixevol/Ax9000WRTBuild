#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace /work

builder_uid="$(id -u builder)"
if [ "$(stat -c '%u' /work)" != "$builder_uid" ]; then
  chown builder:builder /work
fi

for path in /work/*; do
  [ -e "$path" ] || continue
  if [ "$(stat -c '%u' "$path")" != "$builder_uid" ]; then
    chown -R builder:builder "$path"
  fi
done

exec gosu builder "$@"
