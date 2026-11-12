<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SnapshotReadInput

[All wire models](index.md)

Model aliases: `SnapshotReadInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `reader_source_connections` | Array of [`ReaderSourceSelection`](readersourceselection.md) or `null` | No | `null` |
| `snapshot_id` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### reader_source_connections

- anyOf branch 1 (Array of [`ReaderSourceSelection`](readersourceselection.md)): Maximum items: `100`

### snapshot_id

- Minimum length: `1`
- Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "reader_source_connections": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/ReaderSourceSelection"
              },
              "maxItems": 100,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reader Source Connections"
        },
        "snapshot_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Snapshot Id",
          "type": "string"
        }
      },
      "required": [
        "snapshot_id"
      ],
      "title": "SnapshotReadInput",
      "type": "object"
    }
    ```
