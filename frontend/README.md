# firefly koinon frontend

The Angular management app provides Library, Chat, Activity, and role-based Settings. The reusable Angular library and Angular Elements bundle let another application embed those views. The framework-neutral TypeScript SDK is a separate package and has no frontend dependency.

## Local development

Use Node 26 or a supported Angular 22 Node release. Build the SDK in `../sdk/typescript`, then run:

```sh
npm ci
npm start -- --port 18782
```

The development proxy forwards session routes to the local backend on port 18781. Sign-in uses the backend’s OpenID Connect flow. The app sends the CSRF cookie value on session-authenticated writes, including logout. Only the theme preference is stored in browser storage; profile preferences persist through the API.

For the built app, run `npm run build` and `npm run preview`. The preview also serves `/elements/` and the external package consumer at `/consumer/`. Run either preview or the development server on port 18782.

## Packages

- `projects/management`: deployable standalone app and session integration.
- `projects/koinon-angular`: partial-compilation Angular library with a complete initial `/workbench`, compatible root exports, and optional `/chat` and `/settings` entry points, plus focused `/chat/page` and `/chat/evidence` loaders.
- `projects/elements`: `<firefly-koinon>` custom-element registration.
- `smoke/angular-host`: separate Angular application that installs the packed library tarball, without workspace source aliases.

[The library guide](projects/koinon-angular/README.md) describes context inputs, outputs, SDK injection, and optional features. Brand assets and tokens are copied from `../brand` before builds. The host serves the copied assets. Each workbench loads its selected bundled Manrope or Inter variable font from the configured brand asset base and applies it within the widget.

## Code in chat messages

Chat renders backtick and tilde fenced blocks with the reusable `KoinonCodeBlock` atom. Explicit common language names and aliases use [lowlight](https://github.com/wooorm/lowlight) 3.3.0 (MIT), loaded on demand. Unknown or omitted languages remain plain text; no automatic language detection runs. Open fences render through the current end of a streamed message. Inline notation remains prose.

`KoinonCodeBlock` accepts a `language` input and keeps SQL as its default, including the existing SQL tokenizer and **Copy SQL** labels. The tokenizer function stays synchronous for direct consumers; the atom loads it on demand, displays the complete plain text immediately and adds coloring when ready. Highlighting reads only text and token classes from the syntax tree and renders Angular text bindings, never HTML. Unsupported languages, highlighting failures and code over 128 Ki characters retain the complete original text. Copy preserves the code content exactly, including indentation and line endings. Blocks scroll horizontally within their message and inherit the host theme. Attachment references remain interactive in prose and literal inside fenced code.

## Validation

```sh
npm run build
npm test
npm run lint
npm run typecheck
npm run smoke:consumer
npm run test:e2e
npm run check:locale
npm run check:bundle
```

`npm run screenshots` captures responsive review states. Browser tests use controlled HTTP fixtures, which prove frontend contracts and interaction behavior. Integrated authentication, provider execution, and model output need separate live-backend acceptance. A 720-pixel reflow test does not establish actual 200% browser zoom acceptance.

The initial bundle check counts the JavaScript and styles requested by the built management and Elements HTML and enforces the existing 500000-byte warning threshold. `sync:locale` derives Library and panel vocabularies from the canonical Spanish dictionary; builds and tests regenerate them, and `check:locale` detects stale output.

OpenUI uses the official Angular renderer with a registered evidence component library. An artifact identifies an authorized server result; document text, table values, schema, lineage, and citations come from that result. Unsupported components, executable expressions, and mutation actions are rejected. Persisted message cursors support authenticated event replay and retry.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Imported font and brand notices remain with their assets.
