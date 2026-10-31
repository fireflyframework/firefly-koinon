<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KeycloakSettings

[All wire models](index.md)

Model aliases: `KeycloakSettings`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `issuer` | `string` | Yes | Not specified |
| `client_id` | `string` | Yes | Not specified |
| `directory_client_id` | `string` or `null` | No | `null` |
| `membership_mode` | `string` | No | `"direct"` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### kind

- Exact value: `"keycloak"`

### issuer

- Maximum length: `2048`

### client_id

- Minimum length: `1`
- Maximum length: `255`

### directory_client_id

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `255`

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
          "const": "keycloak",
          "title": "Kind",
          "type": "string"
        },
        "issuer": {
          "maxLength": 2048,
          "title": "Issuer",
          "type": "string"
        },
        "client_id": {
          "maxLength": 255,
          "minLength": 1,
          "title": "Client Id",
          "type": "string"
        },
        "directory_client_id": {
          "anyOf": [
            {
              "maxLength": 255,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Directory Client Id"
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
        "issuer",
        "client_id"
      ],
      "title": "KeycloakSettings",
      "type": "object"
    }
    ```
