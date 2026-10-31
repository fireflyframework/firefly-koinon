<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IdentityCheck

[All wire models](index.md)

Model aliases: `IdentityCheck`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `message` | `string` | Yes | Not specified |
| `supported` | `boolean` or `null` | No | `null` |
| `verified` | `boolean` | No | `false` |
| `available` | `boolean` or `null` | No | `null` |
| `observed_at` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"unconfigured"`, `"unknown"`, `"passed"`, `"failed"`, `"blocked"`, `"not_run"`

### observed_at

- anyOf branch 1 (`string`): Format: `"date-time"`


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
        "status": {
          "enum": [
            "unconfigured",
            "unknown",
            "passed",
            "failed",
            "blocked",
            "not_run"
          ],
          "title": "Status",
          "type": "string"
        },
        "message": {
          "title": "Message",
          "type": "string"
        },
        "supported": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Supported"
        },
        "verified": {
          "default": false,
          "title": "Verified",
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
          "default": null,
          "title": "Available"
        },
        "observed_at": {
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
          "title": "Observed At"
        }
      },
      "required": [
        "id",
        "status",
        "message"
      ],
      "title": "IdentityCheck",
      "type": "object"
    }
    ```
