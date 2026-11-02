<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Reference

Use the guides for a complete task and these references for a particular contract, component or architectural boundary.

## API and SDK contracts

The [API and SDK reference](sdk-api.md) connects the complete method index to [API areas](api/index.md), [wire models](models/index.md) and the [SDK runtime reference](sdk-runtime.md). Operation pages explain declared parameters, request and response types, success statuses and headers. Model pages describe required fields, defaults, nullability and validation constraints. The [integration guides](../guides/integrations.md) provide installation, authentication and examples in Python, TypeScript and Java.

## File ingestion policy

[Bounded Library ingestion](library-file-ingestion.md) explains queued 128 MiB originals, synchronous 32 MiB uploads, extraction coverage, durable references and independent resource limits.

## Architecture

- [System architecture](../concepts/architecture.md) describes the application, authorization and persistence boundaries.
- [Knowledge runtime](../concepts/knowledge-runtime.md) explains agents, embeddings and knowledge engines.
- [Backend structure](../concepts/backend-structure.md) describes native pyfly composition and the responsibilities of each layer.
- [MCP architecture](../architecture/mcp.md) describes the connector boundary and authentication.

## Identity and licensing

[Visual identity](../concepts/visual-identity.md) records the Firefly branding system. koinon is distributed under the [Apache License 2.0](../license.md).

## Release evidence

Read the [26.11.5 release notes](../releases/26.11.5.md) for distribution and runtime requirements. The [qualification history](../operations/qualification.md) records checks against specific revisions and environments.
