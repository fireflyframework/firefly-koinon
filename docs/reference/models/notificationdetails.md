<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# NotificationDetails

[All wire models](index.md)

Model aliases: `NotificationDetails`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `label` | `string` or `null` | No | `null` |
| `scopes` | Array of `string` | No | Not specified |
| `expires_at` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### expires_at

- anyOf branch 1 (`string`): Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "label": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Label"
        },
        "scopes": {
          "items": {
            "type": "string"
          },
          "title": "Scopes",
          "type": "array"
        },
        "expires_at": {
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
          "title": "Expires At"
        }
      },
      "title": "NotificationDetails",
      "type": "object"
    }
    ```
