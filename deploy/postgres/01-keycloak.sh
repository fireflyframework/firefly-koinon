#!/bin/sh
# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
set -eu
export KOINON_KEYCLOAK_DB_PASSWORD="$(cat /run/secrets/keycloak_database_password)"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 <<'SQL'
\getenv keycloak_password KOINON_KEYCLOAK_DB_PASSWORD
CREATE ROLE koinon_keycloak LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD :'keycloak_password';
CREATE DATABASE keycloak OWNER koinon_keycloak;
SQL
unset KOINON_KEYCLOAK_DB_PASSWORD
