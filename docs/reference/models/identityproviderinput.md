<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IdentityProviderInput

[All wire models](index.md)

Model aliases: `IdentityProviderInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `broker_alias` | `string` or `null` | No | `null` |
| `settings` | [`KeycloakSettings`](keycloaksettings.md) or [`EntraSettings`](entrasettings.md) or [`GoogleWorkspaceSettings`](googleworkspacesettings.md) | Yes | Not specified |
| `credential` | [`KeycloakCredential`](keycloakcredential.md) or [`EntraCredential`](entracredential.md) or [`GoogleCredential`](googlecredential.md) or `null` | No | `null` |
| `credential_reference` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### kind

- Allowed values: `"keycloak"`, `"entra"`, `"google_workspace"`

### name

- Minimum length: `1`
- Maximum length: `120`

### broker_alias

- anyOf branch 1 (`string`): Pattern: `"^[a-z0-9][a-z0-9_-]{0,63}$"`

### settings

- Discriminator field: `kind`
- For `"entra"`: [`EntraSettings`](entrasettings.md)
- For `"google_workspace"`: [`GoogleWorkspaceSettings`](googleworkspacesettings.md)
- For `"keycloak"`: [`KeycloakSettings`](keycloaksettings.md)

### credential

- anyOf branch 1 ([`KeycloakCredential`](keycloakcredential.md) or [`EntraCredential`](entracredential.md) or [`GoogleCredential`](googlecredential.md)): Discriminator field: `kind`
- anyOf branch 1 ([`KeycloakCredential`](keycloakcredential.md) or [`EntraCredential`](entracredential.md) or [`GoogleCredential`](googlecredential.md)): For `"entra"`: [`EntraCredential`](entracredential.md)
- anyOf branch 1 ([`KeycloakCredential`](keycloakcredential.md) or [`EntraCredential`](entracredential.md) or [`GoogleCredential`](googlecredential.md)): For `"google_workspace"`: [`GoogleCredential`](googlecredential.md)
- anyOf branch 1 ([`KeycloakCredential`](keycloakcredential.md) or [`EntraCredential`](entracredential.md) or [`GoogleCredential`](googlecredential.md)): For `"keycloak"`: [`KeycloakCredential`](keycloakcredential.md)

### credential_reference

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `120`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "kind": {
          "enum": [
            "keycloak",
            "entra",
            "google_workspace"
          ],
          "title": "Kind",
          "type": "string"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "broker_alias": {
          "anyOf": [
            {
              "pattern": "^[a-z0-9][a-z0-9_-]{0,63}$",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Broker Alias"
        },
        "settings": {
          "discriminator": {
            "mapping": {
              "entra": "#/$defs/EntraSettings",
              "google_workspace": "#/$defs/GoogleWorkspaceSettings",
              "keycloak": "#/$defs/KeycloakSettings"
            },
            "propertyName": "kind"
          },
          "oneOf": [
            {
              "$ref": "#/$defs/KeycloakSettings"
            },
            {
              "$ref": "#/$defs/EntraSettings"
            },
            {
              "$ref": "#/$defs/GoogleWorkspaceSettings"
            }
          ],
          "title": "Settings"
        },
        "credential": {
          "anyOf": [
            {
              "discriminator": {
                "mapping": {
                  "entra": "#/$defs/EntraCredential",
                  "google_workspace": "#/$defs/GoogleCredential",
                  "keycloak": "#/$defs/KeycloakCredential"
                },
                "propertyName": "kind"
              },
              "oneOf": [
                {
                  "$ref": "#/$defs/KeycloakCredential"
                },
                {
                  "$ref": "#/$defs/EntraCredential"
                },
                {
                  "$ref": "#/$defs/GoogleCredential"
                }
              ]
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Credential"
        },
        "credential_reference": {
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
          "title": "Credential Reference"
        }
      },
      "required": [
        "kind",
        "name",
        "settings"
      ],
      "title": "IdentityProviderInput",
      "type": "object"
    }
    ```
