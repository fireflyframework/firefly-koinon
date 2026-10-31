<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ModelConnection

[All wire models](index.md)

Model aliases: `ModelConnection`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `ownership` | `string` | Yes | Not specified |
| `read_only` | `boolean` | Yes | Not specified |
| `provider` | `string` or `null` | No | `null` |
| `model_id` | `string` or `null` | No | `null` |
| `configured` | `boolean` | Yes | Not specified |
| `available` | `boolean` or `null` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `reason` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### ownership

- Exact value: `"deployment"`

### read_only

- Exact value: `true`

### status

- Allowed values: `"passed"`, `"failed"`, `"needs_setup"`, `"unverified"`


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
        "ownership": {
          "const": "deployment",
          "title": "Ownership",
          "type": "string"
        },
        "read_only": {
          "const": true,
          "title": "Read Only",
          "type": "boolean"
        },
        "provider": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Provider"
        },
        "model_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Model Id"
        },
        "configured": {
          "title": "Configured",
          "type": "boolean"
        },
        "available": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "title": "Available"
        },
        "status": {
          "enum": [
            "passed",
            "failed",
            "needs_setup",
            "unverified"
          ],
          "title": "Status",
          "type": "string"
        },
        "reason": {
          "title": "Reason",
          "type": "string"
        }
      },
      "required": [
        "id",
        "ownership",
        "read_only",
        "configured",
        "available",
        "status",
        "reason"
      ],
      "title": "ModelConnection",
      "type": "object"
    }
    ```
