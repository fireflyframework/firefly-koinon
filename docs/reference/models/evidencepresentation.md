<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# EvidencePresentation

[All wire models](index.md)

Model aliases: `EvidencePresentation`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `locale` | `string` | No | `"en-US"` |
| `time_zone` | `string` | No | `"UTC"` |
| `response_language` | `string` | No | `"en"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### locale

- Minimum length: `2`
- Maximum length: `64`

### time_zone

- Minimum length: `1`
- Maximum length: `128`

### response_language

- Minimum length: `2`
- Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "locale": {
          "default": "en-US",
          "maxLength": 64,
          "minLength": 2,
          "title": "Locale",
          "type": "string"
        },
        "time_zone": {
          "default": "UTC",
          "maxLength": 128,
          "minLength": 1,
          "title": "Time Zone",
          "type": "string"
        },
        "response_language": {
          "default": "en",
          "maxLength": 64,
          "minLength": 2,
          "title": "Response Language",
          "type": "string"
        }
      },
      "title": "EvidencePresentation",
      "type": "object"
    }
    ```
