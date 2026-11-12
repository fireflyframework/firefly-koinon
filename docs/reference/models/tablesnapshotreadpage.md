<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# TableSnapshotReadPage

[All wire models](index.md)

Model aliases: `TableSnapshotReadPage`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `items` | Array of [`TableSnapshotSummary`](tablesnapshotsummary.md) | Yes | Not specified |
| `next_cursor` | `string` or `null` | Yes | Not specified |
| `total` | `null` | No | `null` |
| `pages` | `null` | No | `null` |
| `total_is_exact` | `boolean` | No | `false` |
| `current_snapshot_id` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### total_is_exact

- Exact value: `false`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "items": {
          "items": {
            "$ref": "#/$defs/TableSnapshotSummary"
          },
          "title": "Items",
          "type": "array"
        },
        "next_cursor": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Next Cursor"
        },
        "total": {
          "default": null,
          "title": "Total",
          "type": "null"
        },
        "pages": {
          "default": null,
          "title": "Pages",
          "type": "null"
        },
        "total_is_exact": {
          "const": false,
          "default": false,
          "title": "Total Is Exact",
          "type": "boolean"
        },
        "current_snapshot_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Current Snapshot Id"
        }
      },
      "required": [
        "items",
        "next_cursor"
      ],
      "title": "TableSnapshotReadPage",
      "type": "object"
    }
    ```
