<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceReplacementPreview

[All wire models](index.md)

Model aliases: `SourceReplacementPreview`.

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
| `parser_fingerprint` | `string` | Yes | Not specified |
| `previous_members` | Array of [`SourcePreviousMember`](sourcepreviousmember.md) | Yes | Not specified |
| `new_members` | Array of [`SourceDiscoveredMember`](sourcediscoveredmember.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### object_id

- Minimum length: `1`
- Maximum length: `64`

### remote_version

- Maximum length: `1024`

### content_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### baseline_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### new_locator_set_sha256

- Pattern: `"^[a-f0-9]{64}$"`

### parser_fingerprint

- Maximum length: `128`

### previous_members

- Minimum items: `1`
- Maximum items: `16`

### new_members

- Minimum items: `1`
- Maximum items: `16`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "object_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Object Id",
          "type": "string"
        },
        "remote_version": {
          "maxLength": 1024,
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
        "parser_fingerprint": {
          "maxLength": 128,
          "title": "Parser Fingerprint",
          "type": "string"
        },
        "previous_members": {
          "items": {
            "$ref": "#/$defs/SourcePreviousMember"
          },
          "maxItems": 16,
          "minItems": 1,
          "title": "Previous Members",
          "type": "array"
        },
        "new_members": {
          "items": {
            "$ref": "#/$defs/SourceDiscoveredMember"
          },
          "maxItems": 16,
          "minItems": 1,
          "title": "New Members",
          "type": "array"
        }
      },
      "required": [
        "object_id",
        "remote_version",
        "content_sha256",
        "baseline_sha256",
        "new_locator_set_sha256",
        "parser_fingerprint",
        "previous_members",
        "new_members"
      ],
      "title": "SourceReplacementPreview",
      "type": "object"
    }
    ```
