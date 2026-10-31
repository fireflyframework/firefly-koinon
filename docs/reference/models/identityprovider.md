<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# IdentityProvider

[All wire models](index.md)

Model aliases: `IdentityProvider`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `name` | `string` | Yes | Not specified |
| `canonical_issuer` | `string` | Yes | Not specified |
| `broker_alias` | `string` or `null` | Yes | Not specified |
| `ownership` | `string` | Yes | Not specified |
| `revision` | `integer` | Yes | Not specified |
| `policy_revision` | `integer` | No | `1` |
| `status` | `string` | Yes | Not specified |
| `credential_configured` | `boolean` | Yes | Not specified |
| `settings` | [`KeycloakSettings`](keycloaksettings.md) or [`EntraSettings`](entrasettings.md) or [`GoogleWorkspaceSettings`](googleworkspacesettings.md) | Yes | Not specified |
| `checks` | Array of [`IdentityCheck`](identitycheck.md) | No | Not specified |
| `capabilities` | Array of `string` | No | Not specified |
| `observed_at` | `string` or `null` | No | `null` |
| `created_at` | `string` or `null` | No | `null` |
| `updated_at` | `string` or `null` | No | `null` |
| `created_by` | `string` or `null` | No | `null` |
| `updated_by` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"keycloak"`, `"entra"`, `"google_workspace"`

### ownership

- Allowed values: `"deployment"`, `"tenant"`

### status

- Allowed values: `"draft"`, `"configured"`, `"blocked"`, `"verified"`, `"active"`, `"disabled"`

### settings

- Discriminator field: `kind`
- For `"entra"`: [`EntraSettings`](entrasettings.md)
- For `"google_workspace"`: [`GoogleWorkspaceSettings`](googleworkspacesettings.md)
- For `"keycloak"`: [`KeycloakSettings`](keycloaksettings.md)

### observed_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### created_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### updated_at

- anyOf branch 1 (`string`): Format: `"date-time"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "title": "Id",
          "type": "string"
        },
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
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
          "title": "Name",
          "type": "string"
        },
        "canonical_issuer": {
          "title": "Canonical Issuer",
          "type": "string"
        },
        "broker_alias": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Broker Alias"
        },
        "ownership": {
          "enum": [
            "deployment",
            "tenant"
          ],
          "title": "Ownership",
          "type": "string"
        },
        "revision": {
          "title": "Revision",
          "type": "integer"
        },
        "policy_revision": {
          "default": 1,
          "title": "Policy Revision",
          "type": "integer"
        },
        "status": {
          "enum": [
            "draft",
            "configured",
            "blocked",
            "verified",
            "active",
            "disabled"
          ],
          "title": "Status",
          "type": "string"
        },
        "credential_configured": {
          "title": "Credential Configured",
          "type": "boolean"
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
        "checks": {
          "items": {
            "$ref": "#/$defs/IdentityCheck"
          },
          "title": "Checks",
          "type": "array"
        },
        "capabilities": {
          "items": {
            "type": "string"
          },
          "title": "Capabilities",
          "type": "array"
        },
        "observed_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Observed At"
        },
        "created_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created At"
        },
        "updated_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Updated At"
        },
        "created_by": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created By"
        },
        "updated_by": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Updated By"
        }
      },
      "required": [
        "id",
        "tenant_id",
        "kind",
        "name",
        "canonical_issuer",
        "broker_alias",
        "ownership",
        "revision",
        "status",
        "credential_configured",
        "settings"
      ],
      "title": "IdentityProvider",
      "type": "object"
    }
    ```
