<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ReplacementResolutionInput

[All wire models](index.md)

Model aliases: `ReplacementResolutionInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `object_id` | `string` | Yes | Not specified |
| `remote_version` | `string` | Yes | Not specified |
| `content_sha256` | `string` | Yes | Not specified |
| `baseline_sha256` | `string` | Yes | Not specified |
| `new_locator_set_sha256` | `string` | Yes | Not specified |
| `replacements` | Array of [`ReplacementMemberInput`](replacementmemberinput.md) | Yes | Not specified |
| `removed_table_ids` | Array of `string` | No | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### object_id

- Minimum length: `1`
- Maximum length: `64`

### remote_version

- Minimum length: `1`
- Maximum length: `1024`

### content_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### baseline_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### new_locator_set_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### replacements

- Minimum items: `1`
- Maximum items: `16`

### removed_table_ids

- Maximum items: `16`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "object_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Object Id",
          "type": "string"
        },
        "remote_version": {
          "maxLength": 1024,
          "minLength": 1,
          "title": "Remote Version",
          "type": "string"
        },
        "content_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Content Sha256",
          "type": "string"
        },
        "baseline_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "Baseline Sha256",
          "type": "string"
        },
        "new_locator_set_sha256": {
          "pattern": "^[a-f0-9]{64}$",
          "title": "New Locator Set Sha256",
          "type": "string"
        },
        "replacements": {
          "items": {
            "$ref": "#/$defs/ReplacementMemberInput"
          },
          "maxItems": 16,
          "minItems": 1,
          "title": "Replacements",
          "type": "array"
        },
        "removed_table_ids": {
          "items": {
            "type": "string"
          },
          "maxItems": 16,
          "title": "Removed Table Ids",
          "type": "array"
        }
      },
      "required": [
        "object_id",
        "remote_version",
        "content_sha256",
        "baseline_sha256",
        "new_locator_set_sha256",
        "replacements"
      ],
      "title": "ReplacementResolutionInput",
      "type": "object"
    }
    ```
