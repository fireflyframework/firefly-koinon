<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Chat and attachments

[All API areas](index.md)

Use the linked wire models for field constraints. Operation metadata does not enumerate every possible HTTP error or replace current server authorization.

## On this page

- [Threads](#assistantcontroller-threads) (GET)
- [Thread create](#assistantcontroller-thread-create) (POST)
- [Messages](#assistantcontroller-messages) (GET)
- [Submit](#assistantcontroller-submit) (POST)
- [Cancel](#assistantcontroller-cancel) (POST)
- [Retry](#assistantcontroller-retry) (POST)
- [Events](#assistantcontroller-events) (GET)
- [Result](#assistantcontroller-result) (GET)
- [Activities](#assistantcontroller-activities) (GET)
- [Audit](#assistantcontroller-audit) (GET)
- [Folders](#chathistorycontroller-folders) (GET)
- [Create folder](#chathistorycontroller-create-folder) (POST)
- [Folder](#chathistorycontroller-folder) (GET)
- [Patch folder](#chathistorycontroller-patch-folder) (PATCH)
- [Delete folder](#chathistorycontroller-delete-folder) (DELETE)
- [Thread](#chathistorycontroller-thread) (GET)
- [Patch thread](#chathistorycontroller-patch-thread) (PATCH)
- [Title suggestion](#chathistorycontroller-title-suggestion) (POST)
- [Capabilities](#chatattachmentscontroller-capabilities) (GET)
- [Upload](#chatattachmentscontroller-upload) (POST)
- [List files](#chatattachmentscontroller-list-files) (GET)
- [Get](#chatattachmentscontroller-get) (GET)
- [Original](#chatattachmentscontroller-original) (GET)
- [Chunks](#chatattachmentscontroller-chunks) (GET)
- [Cancel](#chatattachmentscontroller-cancel) (POST)
- [Retry](#chatattachmentscontroller-retry) (POST)
- [Delete](#chatattachmentscontroller-delete) (DELETE)
- [Knowledge](#chatattachmentscontroller-knowledge) (POST)
- [Get](#organizationchatcontroller-get) (GET)
- [Update](#organizationchatcontroller-update) (PUT)

<!-- operation: AssistantController.threads -->
<a id="assistantcontroller-threads"></a>
## Threads

```http
GET /api/v1/tenants/{tenant_id}/chat/threads
```

Contract operation: `AssistantController.threads`.

| SDK | Method |
| --- | --- |
| Python | `threads` |
| TypeScript | `chat.threads` |
| Java | `client.chat.threads` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `q` | query | `QueryParam[str]` | No | `""` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |
| `sort` | query | `QueryParam[str]` | No | `"updated_at"` |
| `order` | query | `QueryParam[str]` | No | `"desc"` |
| `folder_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `unfiled` | query | `QueryParam[bool]` | No | `false` |
| `project_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `status` | query | `QueryParam[str]` | No | `"active"` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[ChatThread]`](../models/page-chatthread.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AssistantController.thread_create -->
<a id="assistantcontroller-thread-create"></a>
## Thread create

```http
POST /api/v1/tenants/{tenant_id}/chat/threads
```

Contract operation: `AssistantController.thread_create`.

| SDK | Method |
| --- | --- |
| Python | `create_thread` |
| TypeScript | `chat.create` |
| Java | `client.chat.createThread` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ThreadInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ThreadInput`](../models/threadinput.md) |
| Response schema | [`ChatThread`](../models/chatthread.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AssistantController.messages -->
<a id="assistantcontroller-messages"></a>
## Messages

```http
GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/messages
```

Contract operation: `AssistantController.messages`.

| SDK | Method |
| --- | --- |
| Python | `messages` |
| TypeScript | `chat.messages` |
| Java | `client.chat.messages` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |
| `before` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `limit` | query | `QueryParam[int]` | No | `50` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[ChatMessage]`](../models/page-chatmessage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AssistantController.submit -->
<a id="assistantcontroller-submit"></a>
## Submit

```http
POST /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/runs
```

Contract operation: `AssistantController.submit`.

| SDK | Method |
| --- | --- |
| Python | `submit_run` |
| TypeScript | `chat.submit` |
| Java | `client.chat.submit` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[RunInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`RunInput`](../models/runinput.md) |
| Response schema | [`ChatRun`](../models/chatrun.md) |
| Success status | `202` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AssistantController.cancel -->
<a id="assistantcontroller-cancel"></a>
## Cancel

```http
POST /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/cancel
```

Contract operation: `AssistantController.cancel`.

| SDK | Method |
| --- | --- |
| Python | `cancel_run` |
| TypeScript | `chat.cancel` |
| Java | `client.chat.cancel` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`ChatRun`](../models/chatrun.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AssistantController.retry -->
<a id="assistantcontroller-retry"></a>
## Retry

```http
POST /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/retry
```

Contract operation: `AssistantController.retry`.

| SDK | Method |
| --- | --- |
| Python | `retry_run` |
| TypeScript | `chat.retry` |
| Java | `client.chat.retry` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`ChatRun`](../models/chatrun.md) |
| Success status | `202` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AssistantController.events -->
<a id="assistantcontroller-events"></a>
## Events

```http
GET /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/events
```

Contract operation: `AssistantController.events`.

| SDK | Method |
| --- | --- |
| Python | `events` |
| TypeScript | `chat.events` |
| Java | `client.chat.events` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`StreamEvent`](../models/streamevent.md) |
| Success status | `200` |
| Declared encoding | `text/event-stream` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Last-Event-ID (last fully processed opaque event ID)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AssistantController.result -->
<a id="assistantcontroller-result"></a>
## Result

```http
GET /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/results/{result_id}
```

Contract operation: `AssistantController.result`.

| SDK | Method |
| --- | --- |
| Python | `result` |
| TypeScript | `chat.result` |
| Java | `client.chat.result` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |
| `result_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`EvidenceResult`](../models/evidenceresult.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AssistantController.activities -->
<a id="assistantcontroller-activities"></a>
## Activities

```http
GET /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/activity
```

Contract operation: `AssistantController.activities`.

| SDK | Method |
| --- | --- |
| Python | `run_activities` |
| TypeScript | `chat.activities` |
| Java | `client.chat.activities` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[ToolActivity]`](../models/page-toolactivity.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: AssistantController.audit -->
<a id="assistantcontroller-audit"></a>
## Audit

```http
GET /api/v1/tenants/{tenant_id}/chat/runs/{run_id}/audit
```

Contract operation: `AssistantController.audit`.

| SDK | Method |
| --- | --- |
| Python | `run_audit` |
| TypeScript | `chat.audit` |
| Java | `client.chat.audit` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `run_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`AnswerAudit`](../models/answeraudit.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatHistoryController.folders -->
<a id="chathistorycontroller-folders"></a>
## Folders

```http
GET /api/v1/tenants/{tenant_id}/chat/folders
```

Contract operation: `ChatHistoryController.folders`.

| SDK | Method |
| --- | --- |
| Python | `folders` |
| TypeScript | `chat.folders.list` |
| Java | `client.chatFolders.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `q` | query | `QueryParam[str]` | No | `""` |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |
| `parent_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `root_only` | query | `QueryParam[bool]` | No | `false` |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `sort` | query | `QueryParam[str]` | No | `"name"` |
| `order` | query | `QueryParam[str]` | No | `"asc"` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`Page[ChatFolder]`](../models/page-chatfolder.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatHistoryController.create_folder -->
<a id="chathistorycontroller-create-folder"></a>
## Create folder

```http
POST /api/v1/tenants/{tenant_id}/chat/folders
```

Contract operation: `ChatHistoryController.create_folder`.

| SDK | Method |
| --- | --- |
| Python | `create_folder` |
| TypeScript | `chat.folders.create` |
| Java | `client.chatFolders.create` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[FolderCreate]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`FolderCreate`](../models/foldercreate.md) |
| Response schema | [`ChatFolder`](../models/chatfolder.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatHistoryController.folder -->
<a id="chathistorycontroller-folder"></a>
## Folder

```http
GET /api/v1/tenants/{tenant_id}/chat/folders/{folder_id}
```

Contract operation: `ChatHistoryController.folder`.

| SDK | Method |
| --- | --- |
| Python | `folder` |
| TypeScript | `chat.folders.get` |
| Java | `client.chatFolders.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `folder_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`ChatFolder`](../models/chatfolder.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatHistoryController.patch_folder -->
<a id="chathistorycontroller-patch-folder"></a>
## Patch folder

```http
PATCH /api/v1/tenants/{tenant_id}/chat/folders/{folder_id}
```

Contract operation: `ChatHistoryController.patch_folder`.

| SDK | Method |
| --- | --- |
| Python | `update_folder` |
| TypeScript | `chat.folders.update` |
| Java | `client.chatFolders.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `folder_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[FolderPatch]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`FolderPatch`](../models/folderpatch.md) |
| Response schema | [`ChatFolder`](../models/chatfolder.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatHistoryController.delete_folder -->
<a id="chathistorycontroller-delete-folder"></a>
## Delete folder

```http
DELETE /api/v1/tenants/{tenant_id}/chat/folders/{folder_id}
```

Contract operation: `ChatHistoryController.delete_folder`.

| SDK | Method |
| --- | --- |
| Python | `delete_folder` |
| TypeScript | `chat.folders.delete` |
| Java | `client.chatFolders.delete` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `folder_id` | path | `PathVar[str]` | Yes | Not specified |
| `expected_revision` | query | `QueryParam[int]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | No response body |
| Success status | `204` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatHistoryController.thread -->
<a id="chathistorycontroller-thread"></a>
## Thread

```http
GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}
```

Contract operation: `ChatHistoryController.thread`.

| SDK | Method |
| --- | --- |
| Python | `thread` |
| TypeScript | `chat.get` |
| Java | `client.chat.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`ChatThread`](../models/chatthread.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatHistoryController.patch_thread -->
<a id="chathistorycontroller-patch-thread"></a>
## Patch thread

```http
PATCH /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}
```

Contract operation: `ChatHistoryController.patch_thread`.

| SDK | Method |
| --- | --- |
| Python | `update_thread` |
| TypeScript | `chat.update` |
| Java | `client.chat.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[ThreadPatch]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`ThreadPatch`](../models/threadpatch.md) |
| Response schema | [`ChatThread`](../models/chatthread.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatHistoryController.title_suggestion -->
<a id="chathistorycontroller-title-suggestion"></a>
## Title suggestion

```http
POST /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/title-suggestion
```

Contract operation: `ChatHistoryController.title_suggestion`.

| SDK | Method |
| --- | --- |
| Python | `suggest_title` |
| TypeScript | `chat.suggestTitle` |
| Java | `client.chat.suggestTitle` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[TitleRequest]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`TitleRequest`](../models/titlerequest.md) |
| Response schema | [`TitleSuggestion`](../models/titlesuggestion.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatAttachmentsController.capabilities -->
<a id="chatattachmentscontroller-capabilities"></a>
## Capabilities

```http
GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/capabilities
```

Contract operation: `ChatAttachmentsController.capabilities`.

| SDK | Method |
| --- | --- |
| Python | `attachment_capabilities` |
| TypeScript | `chat.attachments.capabilities` |
| Java | `client.chatAttachments.capabilities` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`AttachmentCapabilities`](../models/attachmentcapabilities.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatAttachmentsController.upload -->
<a id="chatattachmentscontroller-upload"></a>
## Upload

```http
POST /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments
```

Contract operation: `ChatAttachmentsController.upload`.

| SDK | Method |
| --- | --- |
| Python | `upload_attachment` |
| TypeScript | `chat.attachments.upload` |
| Java | `client.chatAttachments.upload` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`AttachmentUpload`](../models/attachmentupload.md) |
| Response schema | [`AttachmentView`](../models/attachmentview.md) |
| Success status | `202` |
| Declared encoding | `multipart/form-data` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatAttachmentsController.list_files -->
<a id="chatattachmentscontroller-list-files"></a>
## List files

```http
GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments
```

Contract operation: `ChatAttachmentsController.list_files`.

| SDK | Method |
| --- | --- |
| Python | `attachments` |
| TypeScript | `chat.attachments.list` |
| Java | `client.chatAttachments.list` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |
| `q` | query | `QueryParam[str]` | No | `""` |
| `status` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `kind` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`AttachmentPage`](../models/attachmentpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatAttachmentsController.get -->
<a id="chatattachmentscontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}
```

Contract operation: `ChatAttachmentsController.get`.

| SDK | Method |
| --- | --- |
| Python | `attachment` |
| TypeScript | `chat.attachments.get` |
| Java | `client.chatAttachments.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |
| `attachment_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`AttachmentView`](../models/attachmentview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatAttachmentsController.original -->
<a id="chatattachmentscontroller-original"></a>
## Original

```http
GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}/original
```

Contract operation: `ChatAttachmentsController.original`.

| SDK | Method |
| --- | --- |
| Python | `attachment_original` |
| TypeScript | `chat.attachments.original` |
| Java | `client.chatAttachments.original` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |
| `attachment_id` | path | `PathVar[str]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`BinaryDownload`](../models/binarydownload.md) |
| Success status | `200` |
| Declared encoding | `binary` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatAttachmentsController.chunks -->
<a id="chatattachmentscontroller-chunks"></a>
## Chunks

```http
GET /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}/chunks
```

Contract operation: `ChatAttachmentsController.chunks`.

| SDK | Method |
| --- | --- |
| Python | `attachment_chunks` |
| TypeScript | `chat.attachments.chunks` |
| Java | `client.chatAttachments.chunks` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |
| `attachment_id` | path | `PathVar[str]` | Yes | Not specified |
| `page` | query | `QueryParam[int]` | No | `1` |
| `page_size` | query | `QueryParam[int]` | No | `25` |
| `q` | query | `QueryParam[str]` | No | `""` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`PrivateChunkPage`](../models/privatechunkpage.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatAttachmentsController.cancel -->
<a id="chatattachmentscontroller-cancel"></a>
## Cancel

```http
POST /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}/cancel
```

Contract operation: `ChatAttachmentsController.cancel`.

| SDK | Method |
| --- | --- |
| Python | `cancel_attachment` |
| TypeScript | `chat.attachments.cancel` |
| Java | `client.chatAttachments.cancel` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |
| `attachment_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[AttachmentRevision]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`AttachmentRevision`](../models/attachmentrevision.md) |
| Response schema | [`AttachmentView`](../models/attachmentview.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatAttachmentsController.retry -->
<a id="chatattachmentscontroller-retry"></a>
## Retry

```http
POST /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}/retry
```

Contract operation: `ChatAttachmentsController.retry`.

| SDK | Method |
| --- | --- |
| Python | `retry_attachment` |
| TypeScript | `chat.attachments.retry` |
| Java | `client.chatAttachments.retry` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |
| `attachment_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[AttachmentRevision]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`AttachmentRevision`](../models/attachmentrevision.md) |
| Response schema | [`AttachmentView`](../models/attachmentview.md) |
| Success status | `202` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatAttachmentsController.delete -->
<a id="chatattachmentscontroller-delete"></a>
## Delete

```http
DELETE /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}
```

Contract operation: `ChatAttachmentsController.delete`.

| SDK | Method |
| --- | --- |
| Python | `remove_attachment` |
| TypeScript | `chat.attachments.remove` |
| Java | `client.chatAttachments.remove` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |
| `attachment_id` | path | `PathVar[str]` | Yes | Not specified |
| `expected_revision` | query | `QueryParam[int]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | No response body |
| Success status | `204` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: ChatAttachmentsController.knowledge -->
<a id="chatattachmentscontroller-knowledge"></a>
## Knowledge

```http
POST /api/v1/tenants/{tenant_id}/chat/threads/{thread_id}/attachments/{attachment_id}/knowledge
```

Contract operation: `ChatAttachmentsController.knowledge`.

| SDK | Method |
| --- | --- |
| Python | `promote_attachment` |
| TypeScript | `chat.attachments.promote` |
| Java | `client.chatAttachments.promote` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `thread_id` | path | `PathVar[str]` | Yes | Not specified |
| `attachment_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[AttachmentPromotionInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`AttachmentPromotionInput`](../models/attachmentpromotioninput.md) |
| Response schema | [`AttachmentPromotionView`](../models/attachmentpromotionview.md) |
| Success status | `201` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

- `Idempotency-Key (required; caller-supplied stable operation key)`

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationChatController.get -->
<a id="organizationchatcontroller-get"></a>
## Get

```http
GET /api/v1/tenants/{tenant_id}/chat/settings
```

Contract operation: `OrganizationChatController.get`.

| SDK | Method |
| --- | --- |
| Python | `organization_chat_settings` |
| TypeScript | `organizationChat.get` |
| Java | `client.organizationChat.get` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `workspace_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |
| `project_id` | query | <code>QueryParam&#91;str &#124; None&#93;</code> | No | `null` |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | No request schema declared |
| Response schema | [`OrganizationChatSettings`](../models/organizationchatsettings.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).

<!-- operation: OrganizationChatController.update -->
<a id="organizationchatcontroller-update"></a>
## Update

```http
PUT /api/v1/tenants/{tenant_id}/chat/settings
```

Contract operation: `OrganizationChatController.update`.

| SDK | Method |
| --- | --- |
| Python | `update_organization_chat_settings` |
| TypeScript | `organizationChat.update` |
| Java | `client.organizationChat.update` |

### Parameters

These are the declared path, query and body arguments. Multipart and binary inputs are described by their request schema below. SDK argument names may follow each language’s conventions.

| Name | Location | Declared type | Required | Default |
| --- | --- | --- | --- | --- |
| `tenant_id` | path | `PathVar[str]` | Yes | Not specified |
| `body` | body | `Valid[Body[OrganizationChatSettingsInput]]` | Yes | Not specified |

### Request and response

| Contract | Value |
| --- | --- |
| Request schema | [`OrganizationChatSettingsInput`](../models/organizationchatsettingsinput.md) |
| Response schema | [`OrganizationChatSettings`](../models/organizationchatsettings.md) |
| Success status | `200` |
| Declared encoding | `application/json` |

Encoding identifies the upload, stream or download format when applicable; otherwise it is JSON. It is not a declaration that a GET request has a body.

### Headers

No operation-specific headers are declared in the canonical metadata.

Authentication and resource bounds still apply. See [request behavior](../sdk-api.md#request-behavior) and the [SDK runtime reference](../sdk-runtime.md).
