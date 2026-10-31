<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# GenerationReceipt

[All wire models](index.md)

Model aliases: `GenerationReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `start_sequence` | `integer` | Yes | Not specified |
| `agent_id` | `string` | Yes | Not specified |
| `agent_revision` | `integer` | Yes | Not specified |
| `provider_id` | `string` | Yes | Not specified |
| `provider_revision` | `integer` | Yes | Not specified |
| `provider_kind` | `string` | Yes | Not specified |
| `model_id` | `string` | Yes | Not specified |
| `model_class` | `string` | Yes | Not specified |
| `api` | `string` | Yes | Not specified |
| `binding_output_mode` | `string` or `null` | No | `null` |
| `model_options_sha256` | `string` or `null` | No | `null` |
| `started_at` | `string` | Yes | Not specified |
| `finished_at` | `string` or `null` | No | `null` |
| `status` | `string` | No | `"started"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### start_sequence

- Minimum: `0`

### agent_id

- Minimum length: `1`
- Maximum length: `64`

### agent_revision

- Minimum: `1`

### provider_id

- Minimum length: `1`
- Maximum length: `64`

### provider_revision

- Minimum: `1`

### provider_kind

- Allowed values: `"ollama"`, `"openai"`, `"anthropic"`

### model_id

- Minimum length: `1`
- Maximum length: `255`

### model_class

- Minimum length: `1`
- Maximum length: `128`

### api

- Allowed values: `"chat"`, `"responses"`, `"messages"`

### binding_output_mode

- anyOf branch 1 (`string`): Allowed values: `"default"`, `"native"`

### model_options_sha256

- anyOf branch 1 (`string`): Pattern: `"^[a-f0-9]{64}$"`

### started_at

- Format: `"date-time"`

### finished_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### status

- Allowed values: `"started"`, `"completed"`, `"failed"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Id",
          "type": "string"
        },
        "start_sequence": {
          "minimum": 0,
          "title": "Start Sequence",
          "type": "integer"
        },
        "agent_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Agent Id",
          "type": "string"
        },
        "agent_revision": {
          "minimum": 1,
          "title": "Agent Revision",
          "type": "integer"
        },
        "provider_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Provider Id",
          "type": "string"
        },
        "provider_revision": {
          "minimum": 1,
          "title": "Provider Revision",
          "type": "integer"
        },
        "provider_kind": {
          "enum": [
            "ollama",
            "openai",
            "anthropic"
          ],
          "title": "Provider Kind",
          "type": "string"
        },
        "model_id": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Model Id",
          "type": "string"
        },
        "model_class": {
          "maxLength": 128,
          "minLength": 1,
          "title": "Model Class",
          "type": "string"
        },
        "api": {
          "enum": [
            "chat",
            "responses",
            "messages"
          ],
          "title": "Api",
          "type": "string"
        },
        "binding_output_mode": {
          "anyOf": [
            {
              "enum": [
                "default",
                "native"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Binding Output Mode"
        },
        "model_options_sha256": {
          "anyOf": [
            {
              "pattern": "^[a-f0-9]{64}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Model Options Sha256"
        },
        "started_at": {
          "format": "date-time",
          "title": "Started At",
          "type": "string"
        },
        "finished_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Finished At"
        },
        "status": {
          "default": "started",
          "enum": [
            "started",
            "completed",
            "failed"
          ],
          "title": "Status",
          "type": "string"
        }
      },
      "required": [
        "id",
        "start_sequence",
        "agent_id",
        "agent_revision",
        "provider_id",
        "provider_revision",
        "provider_kind",
        "model_id",
        "model_class",
        "api",
        "started_at"
      ],
      "title": "GenerationReceipt",
      "type": "object"
    }
    ```
