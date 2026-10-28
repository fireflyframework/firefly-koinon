<!-- Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0 -->
# koinon headless SDKs

Use the authenticated knowledge API from Python, TypeScript or Java. The clients support typed requests and responses, file uploads, paginated reads, conversation streaming and recorded source provenance. The backend enforces membership, token scopes and resource permissions on every request.

| Client | Package | Guide |
|---|---|---|
| Python | `firefly-koinon-sdk` | [Async client](python/README.md) |
| TypeScript | `@fireflyframework/koinon-sdk` | [Browser and server transports](typescript/README.md) |
| Java | `org.fireflyframework:koinon-sdk` | [Java 21 client](java/README.md) |

Start with the [headless integration guide](../docs/guides/headless.md). The [shared contract](contract/operations.json) records canonical operations; the [API reference](../docs/reference/sdk-api.md) describes their typed models and methods. Keep tokens in a host-supplied callback and let the host handle renewal. Writes are not automatically retried.

These are development packages. Source tests, installed-package checks, server integration and publication are separate acceptance steps. See the [qualification record](../docs/operations/qualification.md) before rollout.

All three clients use [Apache-2.0](../LICENSE).
