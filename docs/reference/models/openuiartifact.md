<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OpenUIArtifact

[All wire models](index.md)

Model aliases: `OpenUIArtifact`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `language` | `string` | Yes | Not specified |
| `complete` | `boolean` | Yes | Not specified |
| `run_id` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Exact value: `"openui"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "kind": {
          "const": "openui",
          "title": "Kind",
          "type": "string"
        },
        "language": {
          "title": "Language",
          "type": "string"
        },
        "complete": {
          "title": "Complete",
          "type": "boolean"
        },
        "run_id": {
          "title": "Run Id",
          "type": "string"
        }
      },
      "required": [
        "id",
        "kind",
        "language",
        "complete",
        "run_id"
      ],
      "title": "OpenUIArtifact",
      "type": "object"
    }
    ```
