<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# RlmToolReceipt

[All wire models](index.md)

Model aliases: `RlmToolReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `result_id` | `string` | Yes | Not specified |
| `generation_id` | `string` or `null` | No | `null` |
| `tenant_id` | `string` | Yes | Not specified |
| `workspace_id` | `string` | Yes | Not specified |
| `source_ids` | Array of `string` | Yes | Not specified |
| `tool_call_id` | `string` | Yes | Not specified |
| `tool_name` | `string` | Yes | Not specified |
| `request_sha256` | `string` | Yes | Not specified |
| `schema_sha256` | `string` | Yes | Not specified |
| `arguments_sha256` | `string` | Yes | Not specified |
| `result_sha256` | `string` | Yes | Not specified |
| `result_kind` | `string` | Yes | Not specified |
| `execution_sha256` | `string` | Yes | Not specified |
| `outcome` | `string` | Yes | Not specified |
| `execution_status` | `string` | Yes | Not specified |
| `execution_state` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### result_id

- Minimum length: `1`
- Maximum length: `64`

### tenant_id

- Minimum length: `1`
- Maximum length: `64`

### workspace_id

- Minimum length: `1`
- Maximum length: `64`
- Admitted native execution workspace.

### source_ids

- Minimum items: `1`
- Maximum items: `500`
- Admitted native source scope; actual content use requires separate execution-read evidence.

### tool_call_id

- Minimum length: `1`
- Maximum length: `256`

### tool_name

- Allowed values: `"python"`, `"final_answer"`

### request_sha256

- Pattern: `"^[0-9a-f]{64}$"`

### schema_sha256

- Pattern: `"^[0-9a-f]{64}$"`

### arguments_sha256

- Pattern: `"^[0-9a-f]{64}$"`

### result_sha256

- Pattern: `"^[0-9a-f]{64}$"`
- SHA-256 of the actual ToolReturnPart JSON serialization, sorted keys, compact UTF-8.

### result_kind

- Allowed values: `"tool_return"`, `"accepted_final"`, `"execution_failure"`
- tool_return is preserved into subsequent SDK history. accepted_final and execution_failure seal the actual host result locally without asserting a subsequent provider delivery.

### execution_sha256

- Pattern: `"^[0-9a-f]{64}$"`
- SHA-256 of the exact public VM feed dataclass, sorted keys, compact UTF-8.

### outcome

- Allowed values: `"completed"`, `"rejected"`, `"failed"`, `"halted"`

### execution_status

- Minimum length: `1`
- Maximum length: `32`

### execution_state

- Minimum length: `1`
- Maximum length: `32`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "result_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Result Id",
          "type": "string"
        },
        "generation_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Generation Id"
        },
        "tenant_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Tenant Id",
          "type": "string"
        },
        "workspace_id": {
          "description": "Admitted native execution workspace.",
          "maxLength": 64,
          "minLength": 1,
          "title": "Workspace Id",
          "type": "string"
        },
        "source_ids": {
          "description": "Admitted native source scope; actual content use requires separate execution-read evidence.",
          "items": {
            "type": "string"
          },
          "maxItems": 500,
          "minItems": 1,
          "title": "Source Ids",
          "type": "array"
        },
        "tool_call_id": {
          "maxLength": 256,
          "minLength": 1,
          "title": "Tool Call Id",
          "type": "string"
        },
        "tool_name": {
          "enum": [
            "python",
            "final_answer"
          ],
          "title": "Tool Name",
          "type": "string"
        },
        "request_sha256": {
          "pattern": "^[0-9a-f]{64}$",
          "title": "Request Sha256",
          "type": "string"
        },
        "schema_sha256": {
          "pattern": "^[0-9a-f]{64}$",
          "title": "Schema Sha256",
          "type": "string"
        },
        "arguments_sha256": {
          "pattern": "^[0-9a-f]{64}$",
          "title": "Arguments Sha256",
          "type": "string"
        },
        "result_sha256": {
          "description": "SHA-256 of the actual ToolReturnPart JSON serialization, sorted keys, compact UTF-8.",
          "pattern": "^[0-9a-f]{64}$",
          "title": "Result Sha256",
          "type": "string"
        },
        "result_kind": {
          "description": "tool_return is preserved into subsequent SDK history. accepted_final and execution_failure seal the actual host result locally without asserting a subsequent provider delivery.",
          "enum": [
            "tool_return",
            "accepted_final",
            "execution_failure"
          ],
          "title": "Result Kind",
          "type": "string"
        },
        "execution_sha256": {
          "description": "SHA-256 of the exact public VM feed dataclass, sorted keys, compact UTF-8.",
          "pattern": "^[0-9a-f]{64}$",
          "title": "Execution Sha256",
          "type": "string"
        },
        "outcome": {
          "enum": [
            "completed",
            "rejected",
            "failed",
            "halted"
          ],
          "title": "Outcome",
          "type": "string"
        },
        "execution_status": {
          "maxLength": 32,
          "minLength": 1,
          "title": "Execution Status",
          "type": "string"
        },
        "execution_state": {
          "maxLength": 32,
          "minLength": 1,
          "title": "Execution State",
          "type": "string"
        }
      },
      "required": [
        "result_id",
        "tenant_id",
        "workspace_id",
        "source_ids",
        "tool_call_id",
        "tool_name",
        "request_sha256",
        "schema_sha256",
        "arguments_sha256",
        "result_sha256",
        "result_kind",
        "execution_sha256",
        "outcome",
        "execution_status",
        "execution_state"
      ],
      "title": "RlmToolReceipt",
      "type": "object"
    }
    ```
