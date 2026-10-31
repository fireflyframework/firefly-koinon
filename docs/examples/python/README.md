<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Python tutorial source

These complete files accompany the four Python chapters. Use Python 3.12 or later. Download them into one directory so each chapter can import `support.py`.

| File | Purpose |
| --- | --- |
| [startup.py](startup.py) | Complete context and paginated-catalog entry point. |
| [support.py](support.py) | Required environment values and a host-owned bearer callback. |
| [knowledge.py](knowledge.py) | Bounded intake, search/SQL, exact history, reviewed append/replacement and curated intent helpers. |
| [conversations.py](conversations.py) | Scoped runs, checkpointed streaming, revisioned thread moves and reviewed exports/shares. |
| [administration.py](administration.py) | Provider/agent/member helpers, revisioned knowledge settings, index planning and directory operations. |

Install the verified SDK wheel supplied by your operator, then run a read-only entry point:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install "$KOINON_SDK_WHEEL"
python startup.py
```

Set `KOINON_API_URL`, `KOINON_TOKEN`, `KOINON_TENANT_ID` and `KOINON_WORKSPACE_ID` through your secret environment. The API root ends in `/api/v1`. `KOINON_SDK_WHEEL` is a verified local wheel path, not a claim about a package registry.

After choosing an existing document, set `KOINON_DOCUMENT_ID`. The remaining entry points read history, saved threads and the current tenant position, respectively:

```sh
python knowledge.py
python conversations.py
python administration.py
```

Each command has its own current scope requirements. Startup/history need the admitted catalog reads; conversations use the current owner's chat scope; the position self-read uses its profile/tenant boundary. Empty authorized state can return no rows. A 403 requires an authority decision, not automatic scope widening.

Write helpers are defined but are never called by those entry points. Your application supplies reviewed IDs, current revisions, stable operation keys and an actual person decision. In particular, do not call confirmation helpers automatically after creating a preview. The stream helper requires your own durable checkpoint callback, not a print-only replacement.

The chapter functions retain typed return objects. Adapt them inside your host rather than copying an example UUID, provider key or model name. A syntax/type check proves the local contract; running a model, importing a file or changing an organization requires the configured deployment and current authorization.

Return to [Python setup](../../guides/headless-python.md).
