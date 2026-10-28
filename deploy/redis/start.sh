#!/bin/sh
# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
set -eu
umask 077
{
  printf 'bind 0.0.0.0\nprotected-mode yes\nappendonly yes\nappendfsync everysec\n'
  printf 'maxmemory 128mb\nmaxmemory-policy noeviction\ndir /data\n'
  printf 'requirepass %s\n' "$(cat /run/secrets/redis_password)"
} > /tmp/koinon-redis.conf
exec redis-server /tmp/koinon-redis.conf
