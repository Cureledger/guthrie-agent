#!/bin/sh
set -e
# PaaS platforms (e.g. Railway) set PORT; this Eliza stack reads SERVER_PORT (see docker-compose.yaml).
export SERVER_PORT="${PORT:-${SERVER_PORT:-3000}}"
exec elizaos start
