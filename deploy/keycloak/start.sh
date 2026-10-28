#!/bin/sh
# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
set -eu
export KC_DB_PASSWORD="$(cat /run/secrets/keycloak_database_password)"
export KC_BOOTSTRAP_ADMIN_PASSWORD="$(cat /run/secrets/keycloak_admin_password)"
export KOINON_DEMO_PASSWORD="$(cat /run/secrets/demo_password)"
export KOINON_OIDC_CLIENT_SECRET="$(cat /run/secrets/oidc_client_secret)"
exec /opt/keycloak/bin/kc.sh start-dev --import-realm
