<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CommittedKnowledge

[All wire models](index.md)

Model aliases: `CommittedKnowledge`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `status` | `string` | No | `"committed"` |
| `receipt` | [`KnowledgeCommitReceipt`](knowledgecommitreceipt.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Exact value: `"committed"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "status": {
          "const": "committed",
          "default": "committed",
          "title": "Status",
          "type": "string"
        },
        "receipt": {
          "$ref": "#/$defs/KnowledgeCommitReceipt"
        }
      },
      "required": [
        "receipt"
      ],
      "title": "CommittedKnowledge",
      "type": "object"
    }
    ```
