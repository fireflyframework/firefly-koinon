<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# RunInput

[All wire models](index.md)

Model aliases: `RunInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `reader_source_connections` | Array of [`ReaderSourceSelection`](readersourceselection.md) or `null` | No | `null` |
| `attachment_ids` | Array of `string` | No | Not specified |
| `agent_id` | `string` | Yes | Not specified |
| `message` | `string` | Yes | Not specified |
| `scope` | [`KnowledgeScope`](knowledgescope.md) or `null` | No | `null` |
| `client_request_id` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### reader_source_connections

- anyOf branch 1 (Array of [`ReaderSourceSelection`](readersourceselection.md)): Maximum items: `100`

### attachment_ids

- Maximum items: `10`


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
        "attachment_ids": {
          "items": {
            "type": "string"
          },
          "maxItems": 10,
          "title": "Attachment Ids",
          "type": "array"
        },
        "agent_id": {
          "title": "Agent Id",
          "type": "string"
        },
        "message": {
          "title": "Message",
          "type": "string"
        },
        "scope": {
          "anyOf": [
            {
              "$ref": "#/$defs/KnowledgeScope"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "client_request_id": {
          "title": "Client Request Id",
          "type": "string"
        }
      },
      "required": [
        "agent_id",
        "message",
        "client_request_id"
      ],
      "title": "RunInput",
      "type": "object"
    }
    ```
