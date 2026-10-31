<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ProvenanceTransformStep

[All wire models](index.md)

Model aliases: `ProvenanceTransformStep`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `ordinal` | `integer` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `implementation` | `string` | Yes | Not specified |
| `implementation_sha256` | `string` or `null` | No | `null` |
| `input_sha256` | `string` or `null` | No | `null` |
| `output_sha256` | `string` or `null` | No | `null` |
| `parameters` | Map of string keys to [`JsonValue`](jsonvalue.md) | No | Not specified |
| `actor` | `string` | Yes | Not specified |
| `recorded_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Minimum length: `1`
- Maximum length: `64`

### ordinal

- Minimum: `1`
- Maximum: `64`

### kind

- Minimum length: `1`
- Maximum length: `128`

### implementation

- Minimum length: `1`
- Maximum length: `512`

### implementation_sha256

- anyOf branch 1 (`string`): Pattern: `"^[a-f0-9]{64}$"`

### input_sha256

- anyOf branch 1 (`string`): Pattern: `"^[a-f0-9]{64}$"`

### output_sha256

- anyOf branch 1 (`string`): Pattern: `"^[a-f0-9]{64}$"`

### parameters

- Maximum properties: `64`
- Additional properties: [`JsonValue`](jsonvalue.md)

### actor

- Minimum length: `1`
- Maximum length: `512`

### recorded_at

- Format: `"date-time"`


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
        "ordinal": {
          "maximum": 64,
          "minimum": 1,
          "title": "Ordinal",
          "type": "integer"
        },
        "kind": {
          "maxLength": 128,
          "minLength": 1,
          "title": "Kind",
          "type": "string"
        },
        "implementation": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Implementation",
          "type": "string"
        },
        "implementation_sha256": {
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
          "title": "Implementation Sha256"
        },
        "input_sha256": {
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
          "title": "Input Sha256"
        },
        "output_sha256": {
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
          "title": "Output Sha256"
        },
        "parameters": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "maxProperties": 64,
          "title": "Parameters",
          "type": "object"
        },
        "actor": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Actor",
          "type": "string"
        },
        "recorded_at": {
          "format": "date-time",
          "title": "Recorded At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "ordinal",
        "kind",
        "implementation",
        "actor",
        "recorded_at"
      ],
      "title": "ProvenanceTransformStep",
      "type": "object"
    }
    ```
