<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# EvidenceResult

[All wire models](index.md)

Model aliases: `EvidenceResult`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `run_id` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `data` | [`SearchResponse`](searchresponse.md) or [`QueryResponse`](queryresponse.md) or [`DatasetSchema`](datasetschema.md) or [`Lineage`](lineage.md) or [`AttachmentEvidence`](attachmentevidence.md) or [`CatalogProposal`](catalogproposal.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"search"`, `"query"`, `"schema"`, `"lineage"`, `"attachment"`, `"proposal"`


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
        "run_id": {
          "title": "Run Id",
          "type": "string"
        },
        "kind": {
          "enum": [
            "search",
            "query",
            "schema",
            "lineage",
            "attachment",
            "proposal"
          ],
          "title": "Kind",
          "type": "string"
        },
        "data": {
          "anyOf": [
            {
              "$ref": "#/$defs/SearchResponse"
            },
            {
              "$ref": "#/$defs/QueryResponse"
            },
            {
              "$ref": "#/$defs/DatasetSchema"
            },
            {
              "$ref": "#/$defs/Lineage"
            },
            {
              "$ref": "#/$defs/AttachmentEvidence"
            },
            {
              "$ref": "#/$defs/CatalogProposal"
            }
          ],
          "title": "Data"
        }
      },
      "required": [
        "id",
        "run_id",
        "kind",
        "data"
      ],
      "title": "EvidenceResult",
      "type": "object"
    }
    ```
