<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ContentEffects

[All wire models](index.md)

Model aliases: `ContentEffects`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `unchanged` | `boolean` or `null` | No | `null` |
| `affected_asset_ids` | Array of `string` | No | Not specified |
| `snapshot_id` | `string` or `null` | No | `null` |
| `file_id` | `string` or `null` | No | `null` |
| `historical_snapshots_preserved` | `boolean` or `null` | No | `null` |
| `citation_rows_preserved` | `boolean` or `null` | No | `null` |
| `previous_chunk_ids_invalidated` | `boolean` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "unchanged": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Unchanged"
        },
        "affected_asset_ids": {
          "items": {
            "type": "string"
          },
          "title": "Affected Asset Ids",
          "type": "array"
        },
        "snapshot_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Snapshot Id"
        },
        "file_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "File Id"
        },
        "historical_snapshots_preserved": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Historical Snapshots Preserved"
        },
        "citation_rows_preserved": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Citation Rows Preserved"
        },
        "previous_chunk_ids_invalidated": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Previous Chunk Ids Invalidated"
        }
      },
      "title": "ContentEffects",
      "type": "object"
    }
    ```
