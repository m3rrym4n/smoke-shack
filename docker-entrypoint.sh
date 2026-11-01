#!/bin/sh
set -eu

if [ "$(id -u)" -eq 0 ]; then
    mkdir -p /data/photos

    if [ "$(stat -c '%U' /data)" != "smoke" ]; then
        chown -R smoke:smoke /data
    fi

    exec setpriv --reuid=smoke --regid=smoke --init-groups "$@"
fi

exec "$@"
