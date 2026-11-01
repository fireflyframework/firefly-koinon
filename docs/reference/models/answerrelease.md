<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AnswerRelease

[All wire models](index.md)

Supporting wire definition. It is not a separate public model alias in the canonical manifest.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `version` | `integer` | No | `1` |
| `policy_version` | `string` | No | `"knowledge-only-v1"` |
| `run_id` | `string` | Yes | Not specified |
| `message_id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `generation_id` | `string` or `null` | No | `null` |
| `publication_sequence` | `integer` | Yes | Not specified |
| `outcome` | `string` | Yes | Not specified |
| `text_sha256` | `string` | Yes | Not specified |
| `citations_sha256` | `string` | Yes | Not specified |
| `artifacts_sha256` | `string` | Yes | Not specified |
| `policy_sha256` | `string` | Yes | Not specified |
| `fact_ids` | Array of `string` | No | `[]` |
| `result_pins` | Array of [`ResultPin`](resultpin.md) | No | `[]` |
| `source_refs` | Array of [`SourceReference`](sourcereference.md) | No | `[]` |
| `created_at` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### version

- Exact value: `1`

### policy_version

- Exact value: `"knowledge-only-v1"`

### run_id

- Minimum length: `1`
- Maximum length: `64`

### message_id

- Minimum length: `1`
- Maximum length: `64`

### tenant_id

- Minimum length: `1`
- Maximum length: `64`

### publication_sequence

- Minimum: `1`

### outcome

- Allowed values: `"grounded"`, `"refused"`, `"review_required"`

### text_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### citations_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### artifacts_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### policy_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### fact_ids

- Maximum items: `80`

### result_pins

- Maximum items: `100`

### source_refs

- Maximum items: `500`

### created_at

- Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "version": {
          "const": 1,
          "default": 1,
          "title": "Version",
          "type": "integer"
        },
        "policy_version": {
          "const": "knowledge-only-v1",
          "default": "knowledge-only-v1",
          "title": "Policy Version",
          "type": "string"
        },
        "run_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Run Id",
          "type": "string"
        },
        "message_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Message Id",
          "type": "string"
        },
        "tenant_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Tenant Id",
          "type": "string"
        },
        "generation_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Generation Id"
        },
        "publication_sequence": {
          "minimum": 1,
          "title": "Publication Sequence",
          "type": "integer"
        },
        "outcome": {
          "enum": [
            "grounded",
            "refused",
            "review_required"
          ],
          "title": "Outcome",
          "type": "string"
        },
        "text_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Text Sha256",
          "type": "string"
        },
        "citations_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Citations Sha256",
          "type": "string"
        },
        "artifacts_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Artifacts Sha256",
          "type": "string"
        },
        "policy_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Policy Sha256",
          "type": "string"
        },
        "fact_ids": {
          "default": [],
          "items": {
            "type": "string"
          },
          "maxItems": 80,
          "title": "Fact Ids",
          "type": "array"
        },
        "result_pins": {
          "default": [],
          "items": {
            "$ref": "#/$defs/ResultPin"
          },
          "maxItems": 100,
          "title": "Result Pins",
          "type": "array"
        },
        "source_refs": {
          "default": [],
          "items": {
            "$ref": "#/$defs/SourceReference"
          },
          "maxItems": 500,
          "title": "Source Refs",
          "type": "array"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        }
      },
      "required": [
        "run_id",
        "message_id",
        "tenant_id",
        "publication_sequence",
        "outcome",
        "text_sha256",
        "citations_sha256",
        "artifacts_sha256",
        "policy_sha256",
        "created_at"
      ],
      "title": "AnswerRelease",
      "type": "object"
    }
    ```
