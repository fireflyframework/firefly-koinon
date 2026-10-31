<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IdentityProviderPatch

[All wire models](index.md)

Model aliases: `IdentityProviderPatch`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `expected_revision` | `integer` | Yes | Not specified |
| `name` | `string` or `null` | No | `null` |
| `settings` | [`KeycloakSettings`](keycloaksettings.md) or [`EntraSettings`](entrasettings.md) or [`GoogleWorkspaceSettings`](googleworkspacesettings.md) or `null` | No | `null` |
| `credential` | [`KeycloakCredential`](keycloakcredential.md) or [`EntraCredential`](entracredential.md) or [`GoogleCredential`](googlecredential.md) or `null` | No | `null` |
| `credential_reference` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### expected_revision

- Minimum: `1`

### name

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `120`

### settings

- anyOf branch 1 ([`KeycloakSettings`](keycloaksettings.md) or [`EntraSettings`](entrasettings.md) or [`GoogleWorkspaceSettings`](googleworkspacesettings.md)): Discriminator field: `kind`
- anyOf branch 1 ([`KeycloakSettings`](keycloaksettings.md) or [`EntraSettings`](entrasettings.md) or [`GoogleWorkspaceSettings`](googleworkspacesettings.md)): For `"entra"`: [`EntraSettings`](entrasettings.md)
- anyOf branch 1 ([`KeycloakSettings`](keycloaksettings.md) or [`EntraSettings`](entrasettings.md) or [`GoogleWorkspaceSettings`](googleworkspacesettings.md)): For `"google_workspace"`: [`GoogleWorkspaceSettings`](googleworkspacesettings.md)
- anyOf branch 1 ([`KeycloakSettings`](keycloaksettings.md) or [`EntraSettings`](entrasettings.md) or [`GoogleWorkspaceSettings`](googleworkspacesettings.md)): For `"keycloak"`: [`KeycloakSettings`](keycloaksettings.md)

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
        "expected_revision": {
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
        "settings": {
          "anyOf": [
            {
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
              ]
            },
            {
              "type": "null"
            }
          ],
          "default": null,
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
        "expected_revision"
      ],
      "title": "IdentityProviderPatch",
      "type": "object"
    }
    ```
