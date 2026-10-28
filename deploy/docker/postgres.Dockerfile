# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
FROM postgres:17.11-bookworm
ARG PGVECTOR_VERSION=0.8.7
ARG PGVECTOR_SHA256=cac0b10c360f05b2d521200105ba3697e773d4cd3731f5a915a7e37ebe0bea85
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl ca-certificates postgresql-server-dev-17 \
 && curl --fail --location "https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v${PGVECTOR_VERSION}" -o /tmp/pgvector.tar.gz \
 && echo "${PGVECTOR_SHA256}  /tmp/pgvector.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/pgvector.tar.gz -C /tmp \
 && make -C "/tmp/pgvector-${PGVECTOR_VERSION}" -j2 PG_CONFIG=/usr/lib/postgresql/17/bin/pg_config \
 && make -C "/tmp/pgvector-${PGVECTOR_VERSION}" install PG_CONFIG=/usr/lib/postgresql/17/bin/pg_config \
 && rm -rf /tmp/pgvector* /var/lib/apt/lists/*
