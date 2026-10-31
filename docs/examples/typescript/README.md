<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# TypeScript tutorial source

These complete Node.js 22+ modules use the framework-neutral SDK. Download all source files and the compiler configuration into one directory. The `.mts` extension emits native `.mjs` modules; local imports therefore use their final `.mjs` names.

| File | Purpose |
| --- | --- |
| [startup.mts](startup.mts) | Context and lazy catalog paging entry point. |
| [support.mts](support.mts) | Environment validation and a host-owned bearer callback. |
| [knowledge.mts](knowledge.mts) | Intake, search/SQL, immutable history, reviewed append/replacement and curated changes. |
| [conversations.mts](conversations.mts) | Scoped runs, checkpointed SSE, thread moves and reviewed exports/shares. |
| [administration.mts](administration.mts) | Typed provider/agent/member changes, RAG/RLM settings, index planning and directory operations. |
| [tsconfig.json](tsconfig.json) | Strict NodeNext compilation with DOM and Node API types. |

Create your host package and install the operator's verified local SDK archive. TypeScript and Node declarations are development dependencies; the SDK itself comes from the selected archive rather than an assumed registry publication.

```sh
npm init -y
npm install "$KOINON_SDK_PACKAGE"
npm install --save-dev typescript @types/node
npx tsc -p tsconfig.json
node dist/startup.mjs
```

Set `KOINON_API_URL`, `KOINON_TOKEN`, `KOINON_TENANT_ID` and `KOINON_WORKSPACE_ID` through your approved secret environment. The API root ends in `/api/v1`; `KOINON_SDK_PACKAGE` is a verified local `.tgz` path. The callback is evaluated per request. Replace its environment lookup with your host's token-renewal callback for an expiring access token.

The other entry points read an existing document's versions, the owner's saved threads and the current tenant position:

```sh
node dist/knowledge.mjs
node dist/conversations.mjs
node dist/administration.mjs
```

The history entry point additionally needs `KOINON_DOCUMENT_ID`. Each command requires its current API scopes and resource bounds; an empty authorized page is valid. The files contain write helpers, but their entry points never call them. Your host supplies actual reviewed inputs and confirmation; a function parameter is not evidence that a person approved a change.

The event helper requires a durable callback that stores presentation state and cursor together. The caller owns `AbortController` and any Blob URL created from a private download. Closing or aborting HTTP does not cancel a durable server run, job or export. The modules are safe to import: their read-only entry points run only when the corresponding file is invoked directly. Your host can import a helper without starting its default request.

Return to [TypeScript setup](../../guides/headless-typescript.md).
