<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# NotificationTarget

[All wire models](index.md)

Model aliases: `NotificationTarget`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `id` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"invitation"`, `"workspace"`, `"access"`, `"none"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "kind": {
          "enum": [
            "invitation",
            "workspace",
            "access",
            "none"
          ],
          "title": "Kind",
          "type": "string"
        },
        "id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Id"
        }
      },
      "required": [
        "kind"
      ],
      "title": "NotificationTarget",
      "type": "object"
    }
    ```
