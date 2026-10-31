<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KeycloakCredential

[All wire models](index.md)

Model aliases: `KeycloakCredential`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `secret` | `string` | Yes | Not specified |
| `directory_secret` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### kind

- Exact value: `"keycloak"`

### secret

- Minimum length: `1`
- Maximum length: `8192`
- Format: `"password"`
- Write only: `true`

### directory_secret

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `8192`
- anyOf branch 1 (`string`): Format: `"password"`
- anyOf branch 1 (`string`): Write only: `true`


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
        "secret": {
          "format": "password",
          "maxLength": 8192,
          "minLength": 1,
          "title": "Secret",
          "type": "string",
          "writeOnly": true
        },
        "directory_secret": {
          "anyOf": [
            {
              "format": "password",
              "maxLength": 8192,
              "minLength": 1,
              "type": "string",
              "writeOnly": true
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Directory Secret"
        }
      },
      "required": [
        "kind",
        "secret"
      ],
      "title": "KeycloakCredential",
      "type": "object"
    }
    ```
