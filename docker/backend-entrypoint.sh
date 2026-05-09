#!/usr/bin/env sh
set -eu

if [ -S /var/run/docker.sock ]; then
    group_id="$(stat -c '%g' /var/run/docker.sock)"
    if ! getent group "$group_id" >/dev/null 2>&1; then
        addgroup --gid "$group_id" docker-host >/dev/null 2>&1 || true
    fi
fi

exec "$@"
