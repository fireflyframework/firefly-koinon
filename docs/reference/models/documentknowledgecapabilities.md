<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DocumentKnowledgeCapabilities

[All wire models](index.md)

Model aliases: `DocumentKnowledgeCapabilities`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `answer_modes` | Array of `string` | Yes | Not specified |
| `rlm_curated_knowledge_supported` | `boolean` | Yes | Not specified |
| `rlm_curated_knowledge_reason` | `string` | Yes | Not specified |
| `rlm_model_role` | `string` | Yes | Not specified |
| `rlm_recorded_views_required` | `boolean` | Yes | Not specified |
| `rlm_recorded_views_reason` | `string` | Yes | Not specified |
| `bounds` | [`DocumentKnowledgeBounds`](documentknowledgebounds.md) | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### answer_modes

- Each item: Allowed values: `"rag"`, `"rlm"`

### rlm_curated_knowledge_reason

- Exact value: `"KNOWLEDGE_RLM_UNQUALIFIED"`

### rlm_model_role

- Exact value: `"documents.rlm"`

### rlm_recorded_views_required

- Exact value: `true`

### rlm_recorded_views_reason

- Exact value: `"RLM_DOCUMENT_VIEWS_REQUIRED"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "answer_modes": {
          "items": {
            "enum": [
              "rag",
              "rlm"
            ],
            "type": "string"
          },
          "title": "Answer Modes",
          "type": "array"
        },
        "rlm_curated_knowledge_supported": {
          "title": "Rlm Curated Knowledge Supported",
          "type": "boolean"
        },
        "rlm_curated_knowledge_reason": {
          "const": "KNOWLEDGE_RLM_UNQUALIFIED",
          "title": "Rlm Curated Knowledge Reason",
          "type": "string"
        },
        "rlm_model_role": {
          "const": "documents.rlm",
          "title": "Rlm Model Role",
          "type": "string"
        },
        "rlm_recorded_views_required": {
          "const": true,
          "title": "Rlm Recorded Views Required",
          "type": "boolean"
        },
        "rlm_recorded_views_reason": {
          "const": "RLM_DOCUMENT_VIEWS_REQUIRED",
          "title": "Rlm Recorded Views Reason",
          "type": "string"
        },
        "bounds": {
          "$ref": "#/$defs/DocumentKnowledgeBounds"
        }
      },
      "required": [
        "answer_modes",
        "rlm_curated_knowledge_supported",
        "rlm_curated_knowledge_reason",
        "rlm_model_role",
        "rlm_recorded_views_required",
        "rlm_recorded_views_reason",
        "bounds"
      ],
      "title": "DocumentKnowledgeCapabilities",
      "type": "object"
    }
    ```
