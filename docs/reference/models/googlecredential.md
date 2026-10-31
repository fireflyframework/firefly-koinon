<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# GoogleCredential

[All wire models](index.md)

Model aliases: `GoogleCredential`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `secret` | `string` or `null` | No | `null` |
| `service_account_email` | `string` or `null` | No | `null` |
| `private_key` | `string` or `null` | No | `null` |
| `private_key_id` | `string` or `null` | No | `null` |
| `delegated_admin` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### kind

- Exact value: `"google_workspace"`

### secret

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `8192`
- anyOf branch 1 (`string`): Format: `"password"`
- anyOf branch 1 (`string`): Write only: `true`

### service_account_email

- anyOf branch 1 (`string`): Maximum length: `320`

### private_key

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `32768`
- anyOf branch 1 (`string`): Format: `"password"`
- anyOf branch 1 (`string`): Write only: `true`

### private_key_id

- anyOf branch 1 (`string`): Maximum length: `255`

### delegated_admin

- anyOf branch 1 (`string`): Maximum length: `320`


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
        "secret": {
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
          "title": "Secret"
        },
        "service_account_email": {
          "anyOf": [
            {
              "maxLength": 320,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Service Account Email"
        },
        "private_key": {
          "anyOf": [
            {
              "format": "password",
              "maxLength": 32768,
              "minLength": 1,
              "type": "string",
              "writeOnly": true
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Private Key"
        },
        "private_key_id": {
          "anyOf": [
            {
              "maxLength": 255,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Private Key Id"
        },
        "delegated_admin": {
          "anyOf": [
            {
              "maxLength": 320,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Delegated Admin"
        }
      },
      "required": [
        "kind"
      ],
      "title": "GoogleCredential",
      "type": "object"
    }
    ```
