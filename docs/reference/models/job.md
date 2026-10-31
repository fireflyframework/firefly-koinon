<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Job

[All wire models](index.md)

Model aliases: `Job`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `resource_id` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `attempts` | `integer` | Yes | Not specified |
| `max_attempts` | `integer` | Yes | Not specified |
| `progress` | `integer` | Yes | Not specified |
| `error` | `string` or `null` | No | `null` |
| `result` | Map of string keys to [`JsonValue`](jsonvalue.md) or `null` | No | `null` |
| `created_at` | `string` | Yes | Not specified |
| `updated_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### result

- anyOf branch 1 (Map of string keys to [`JsonValue`](jsonvalue.md)): Additional properties: [`JsonValue`](jsonvalue.md)


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
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "resource_id": {
          "title": "Resource Id",
          "type": "string"
        },
        "kind": {
          "title": "Kind",
          "type": "string"
        },
        "status": {
          "title": "Status",
          "type": "string"
        },
        "attempts": {
          "title": "Attempts",
          "type": "integer"
        },
        "max_attempts": {
          "title": "Max Attempts",
          "type": "integer"
        },
        "progress": {
          "title": "Progress",
          "type": "integer"
        },
        "error": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Error"
        },
        "result": {
          "anyOf": [
            {
              "additionalProperties": {
                "$ref": "#/$defs/JsonValue"
              },
              "type": "object"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Result"
        },
        "created_at": {
          "title": "Created At",
          "type": "string"
        },
        "updated_at": {
          "title": "Updated At",
          "type": "string"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "resource_id",
        "kind",
        "status",
        "attempts",
        "max_attempts",
        "progress",
        "created_at",
        "updated_at"
      ],
      "title": "Job",
      "type": "object"
    }
    ```
