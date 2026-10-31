<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExternalProposalEvidence

[All wire models](index.md)

Model aliases: `ExternalProposalEvidence`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | No | `"external_proposal"` |
| `text` | `string` | Yes | Not specified |
| `sha256` | `string` | Yes | Not specified |
| `submitted_by` | `string` | Yes | Not specified |
| `credential_id` | `string` | Yes | Not specified |
| `application_id` | `string` or `null` | No | `null` |
| `source_receipt_ids` | Array of `string` | No | `[]` |
| `recorded_at` | `string` | Yes | Not specified |
| `authority` | `string` | No | `"unverified"` |
| `provider` | `null` | No | `null` |
| `model` | `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Exact value: `"external_proposal"`

### text

- Minimum length: `1`
- Maximum length: `262144`

### sha256

- Pattern: `"^[a-f0-9]{64}$"`

### submitted_by

- Minimum length: `1`
- Maximum length: `512`

### credential_id

- Minimum length: `1`
- Maximum length: `64`

### application_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `64`

### source_receipt_ids

- Maximum items: `32`
- Each item: Minimum length: `1`
- Each item: Maximum length: `64`

### recorded_at

- Format: `"date-time"`

### authority

- Exact value: `"unverified"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "kind": {
          "const": "external_proposal",
          "default": "external_proposal",
          "title": "Kind",
          "type": "string"
        },
        "text": {
          "maxLength": 262144,
          "minLength": 1,
          "title": "Text",
          "type": "string"
        },
        "sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Sha256",
          "type": "string"
        },
        "submitted_by": {
          "maxLength": 512,
          "minLength": 1,
          "title": "Submitted By",
          "type": "string"
        },
        "credential_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Credential Id",
          "type": "string"
        },
        "application_id": {
          "anyOf": [
            {
              "maxLength": 64,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Application Id"
        },
        "source_receipt_ids": {
          "default": [],
          "items": {
            "maxLength": 64,
            "minLength": 1,
            "type": "string"
          },
          "maxItems": 32,
          "title": "Source Receipt Ids",
          "type": "array"
        },
        "recorded_at": {
          "format": "date-time",
          "title": "Recorded At",
          "type": "string"
        },
        "authority": {
          "const": "unverified",
          "default": "unverified",
          "title": "Authority",
          "type": "string"
        },
        "provider": {
          "default": null,
          "title": "Provider",
          "type": "null"
        },
        "model": {
          "default": null,
          "title": "Model",
          "type": "null"
        }
      },
      "required": [
        "text",
        "sha256",
        "submitted_by",
        "credential_id",
        "recorded_at"
      ],
      "title": "ExternalProposalEvidence",
      "type": "object"
    }
    ```
