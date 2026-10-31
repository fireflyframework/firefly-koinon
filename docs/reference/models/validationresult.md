<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ValidationResult

[All wire models](index.md)

Model aliases: `ValidationResult`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `connected` | `boolean` | No | `false` |
| `discovered` | `boolean` | No | `false` |
| `provider_id` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `checks` | Array of [`SetupCheck`](setupcheck.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"ready"`, `"needs_setup"`, `"unverified"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "connected": {
          "default": false,
          "title": "Connected",
          "type": "boolean"
        },
        "discovered": {
          "default": false,
          "title": "Discovered",
          "type": "boolean"
        },
        "provider_id": {
          "title": "Provider Id",
          "type": "string"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "status": {
          "enum": [
            "ready",
            "needs_setup",
            "unverified"
          ],
          "title": "Status",
          "type": "string"
        },
        "checks": {
          "items": {
            "$ref": "#/$defs/SetupCheck"
          },
          "title": "Checks",
          "type": "array"
        }
      },
      "required": [
        "provider_id",
        "revision",
        "status",
        "checks"
      ],
      "title": "ValidationResult",
      "type": "object"
    }
    ```
