<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# McpOAuthClientValues

[All wire models](index.md)

Model aliases: `McpOAuthClientValues`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Not specified |
| `redirect_uris` | Array of `string` | Yes | Not specified |
| `scopes` | Array of `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### name

- Minimum length: `1`
- Maximum length: `120`

### redirect_uris

- Minimum items: `1`
- Maximum items: `8`

### scopes

- Minimum items: `1`
- Maximum items: `8`
- Each item: Allowed values: `"catalog:read"`, `"catalog:write"`, `"ingest:write"`, `"knowledge:search"`, `"query:execute"`, `"chat:use"`, `"evidence:read"`, `"activity:read"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "redirect_uris": {
          "items": {
            "type": "string"
          },
          "maxItems": 8,
          "minItems": 1,
          "title": "Redirect Uris",
          "type": "array"
        },
        "scopes": {
          "items": {
            "enum": [
              "catalog:read",
              "catalog:write",
              "ingest:write",
              "knowledge:search",
              "query:execute",
              "chat:use",
              "evidence:read",
              "activity:read"
            ],
            "type": "string"
          },
          "maxItems": 8,
          "minItems": 1,
          "title": "Scopes",
          "type": "array"
        }
      },
      "required": [
        "name",
        "redirect_uris",
        "scopes"
      ],
      "title": "McpOAuthClientValues",
      "type": "object"
    }
    ```
