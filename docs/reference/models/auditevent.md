<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AuditEvent

[All wire models](index.md)

Model aliases: `AuditEvent`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `subject` | `string` | Yes | Not specified |
| `action` | `string` | Yes | Not specified |
| `resource_id` | `string` or `null` | No | `null` |
| `details` | Map of string keys to [`JsonValue`](jsonvalue.md) | No | Not specified |
| `created_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### details

- Additional properties: [`JsonValue`](jsonvalue.md)


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
        "subject": {
          "title": "Subject",
          "type": "string"
        },
        "action": {
          "title": "Action",
          "type": "string"
        },
        "resource_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Resource Id"
        },
        "details": {
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          },
          "title": "Details",
          "type": "object"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "subject",
        "action",
        "created_at"
      ],
      "title": "AuditEvent",
      "type": "object"
    }
    ```
