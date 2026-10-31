<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ConnectionPool

[All wire models](index.md)

Model aliases: `ConnectionPool`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `size` | `integer` or `null` | No | `null` |
| `max_overflow` | `integer` or `null` | No | `null` |
| `timeout` | `number` or `null` | No | `null` |
| `recycle` | `integer` | Yes | Not specified |
| `pre_ping` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "size": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Size"
        },
        "max_overflow": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Max Overflow"
        },
        "timeout": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Timeout"
        },
        "recycle": {
          "title": "Recycle",
          "type": "integer"
        },
        "pre_ping": {
          "title": "Pre Ping",
          "type": "boolean"
        }
      },
      "required": [
        "recycle",
        "pre_ping"
      ],
      "title": "ConnectionPool",
      "type": "object"
    }
    ```
