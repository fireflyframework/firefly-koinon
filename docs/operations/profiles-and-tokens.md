# Profiles and personal access tokens

A profile belongs to the canonical verified issuer/subject pair. Initial display name and locale come only from verified identity claims; self edits never change identity, roles or memberships. Use `GET/PATCH /api/v1/profile` or the browser BFF projection. Allowed preferences are `display_name`, `locale`, `time_zone` and `response_language`; timezone values must exist in the IANA database. Machine-readable API values remain canonical. Applications apply formatting in their presentation layer and preserve per-answer presentation metadata when available.

Upload an avatar as raw PNG, JPEG or WebP bytes to `POST /profile/avatar` with the corresponding Content-Type. The limit is 2 MiB and 4096 pixels per side. Animated images and SVG are rejected. The service creates a fresh JPEG thumbnail of at most 128 pixels per side, strips metadata and stores only that thumbnail in PostgreSQL. It never fetches an external avatar URL. Authenticated GET returns JPEG with private conditional caching; DELETE removes it. Directory avatars are reauthorized before even a conditional 304 response.

Member lookup requires `members:write` in the selected validated tenant/workspace. It returns active member names and avatars without private locale/timezone preferences or email. Catalog actor summaries are available only after content authorization and are deduplicated by subject. Display names and pictures are presentation data, never authorization keys.

Create personal access tokens through an interactive verified identity. `GET /tokens/scopes?tenant_id=...&workspace_id=...` returns current scope descriptors and policy bounds. `POST /tokens` accepts a name, tenant, explicit scopes, aware ISO expiry, and optional workspace/asset limits. The default policy permits at most 100 active tokens per owner and expiry up to 365 days. Restrict tokens to the smallest useful scope and lifetime. Management scopes require organization scope.

The token secret is returned once at creation. Store it in a secret manager; list responses expose metadata only. The database stores a digest, not the plaintext credential. Send the token as an API bearer credential. It cannot mint more tokens. `DELETE /tokens/{id}` revokes it. Authentication rechecks expiry/revocation; governed reads/writes intersect current owner memberships and resource limits, and delegated durable chat retains the originating token restriction.

Profile scopes are separate: a search-only token cannot read or change the owner's profile. `profile:write` includes profile read. Directory operations additionally enforce tenant/workspace bounds. SDK token callbacks can supply either an OIDC access token or a personal token and are reread for each request. The SDK never retries writes automatically.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.
