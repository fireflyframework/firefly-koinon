<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# McpOAuthClientPatch

[All wire models](index.md)

Model aliases: `McpOAuthClientPatch`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `name` | `string` or `null` | No | `null` |
| `redirect_uris` | Array of `string` or `null` | No | `null` |
| `scopes` | Array of `string` or `null` | No | `null` |
| `enabled` | `boolean` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `1`
- Maximum: `2147483646`

### name

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `120`

### redirect_uris

- anyOf branch 1 (Array of `string`): Minimum items: `1`
- anyOf branch 1 (Array of `string`): Maximum items: `8`

### scopes

- anyOf branch 1 (Array of `string`): Minimum items: `1`
- anyOf branch 1 (Array of `string`): Maximum items: `7`
- anyOf branch 1 (Array of `string`): Each item: Allowed values: `"catalog:read"`, `"catalog:write"`, `"ingest:write"`, `"knowledge:search"`, `"query:execute"`, `"chat:use"`, `"evidence:read"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "expected_revision": {
          "maximum": 2147483646,
          "minimum": 1,
          "title": "Expected Revision",
          "type": "integer"
        },
        "name": {
          "anyOf": [
            {
              "maxLength": 120,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Name"
        },
        "redirect_uris": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "maxItems": 8,
              "minItems": 1,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Redirect Uris"
        },
        "scopes": {
          "anyOf": [
            {
              "items": {
                "enum": [
                  "catalog:read",
                  "catalog:write",
                  "ingest:write",
                  "knowledge:search",
                  "query:execute",
                  "chat:use",
                  "evidence:read"
                ],
                "type": "string"
              },
              "maxItems": 7,
              "minItems": 1,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Scopes"
        },
        "enabled": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Enabled"
        }
      },
      "required": [
        "expected_revision"
      ],
      "title": "McpOAuthClientPatch",
      "type": "object"
    }
    ```
