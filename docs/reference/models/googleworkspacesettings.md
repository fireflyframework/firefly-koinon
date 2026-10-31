<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# GoogleWorkspaceSettings

[All wire models](index.md)

Model aliases: `GoogleWorkspaceSettings`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `client_id` | `string` | Yes | Not specified |
| `hosted_domains` | Array of `string` | Yes | Not specified |
| `customer_id` | `string` or `null` | No | `null` |
| `membership_mode` | `string` | No | `"direct"` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### kind

- Exact value: `"google_workspace"`

### client_id

- Minimum length: `1`
- Maximum length: `255`

### hosted_domains

- Minimum items: `1`
- Maximum items: `10`

### customer_id

- anyOf branch 1 (`string`): Maximum length: `128`

### membership_mode

- Allowed values: `"direct"`, `"transitive"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "const": "google_workspace",
          "title": "Kind",
          "type": "string"
        },
        "client_id": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Client Id",
          "type": "string"
        },
        "hosted_domains": {
          "items": {
            "type": "string"
          },
          "maxItems": 10,
          "minItems": 1,
          "title": "Hosted Domains",
          "type": "array"
        },
        "customer_id": {
          "anyOf": [
            {
              "maxLength": 128,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Customer Id"
        },
        "membership_mode": {
          "default": "direct",
          "enum": [
            "direct",
            "transitive"
          ],
          "title": "Membership Mode",
          "type": "string"
        }
      },
      "required": [
        "kind",
        "client_id",
        "hosted_domains"
      ],
      "title": "GoogleWorkspaceSettings",
      "type": "object"
    }
    ```
