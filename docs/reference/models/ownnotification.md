<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OwnNotification

[All wire models](index.md)

Model aliases: `OwnNotification`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `workspace_name` | `string` or `null` | No | `null` |
| `actor_name` | `string` or `null` | No | `null` |
| `details` | [`NotificationDetails`](notificationdetails.md) or `null` | No | `null` |
| `id` | `string` | Yes | Not specified |
| `kind` | `string` | Yes | Not specified |
| `title` | `string` | Yes | Not specified |
| `body` | `string` | Yes | Not specified |
| `created_at` | `string` | Yes | Not specified |
| `read_at` | `string` or `null` | Yes | Not specified |
| `tenant_id` | `string` | Yes | Not specified |
| `organization_name` | `string` | Yes | Not specified |
| `target` | [`NotificationTarget`](notificationtarget.md) | Yes | Not specified |
| `effective_locale` | `string` | No | `"en-US"` |
| `locale_origin` | `string` | No | `"default"` |
| `powered_by` | `string` | No | `"Powered by koinon"` |
| `copyright` | `string` | No | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Allowed values: `"invitation"`, `"access_granted"`, `"role_changed"`, `"access_removed"`, `"security"`, `"welcome"`, `"digest"`

### created_at

- Format: `"date-time"`

### read_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### locale_origin

- Allowed values: `"user"`, `"organization"`, `"installation"`, `"default"`

### powered_by

- Exact value: `"Powered by koinon"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "workspace_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Workspace Name"
        },
        "actor_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Actor Name"
        },
        "details": {
          "anyOf": [
            {
              "$ref": "#/$defs/NotificationDetails"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "id": {
          "title": "Id",
          "type": "string"
        },
        "kind": {
          "enum": [
            "invitation",
            "access_granted",
            "role_changed",
            "access_removed",
            "security",
            "welcome",
            "digest"
          ],
          "title": "Kind",
          "type": "string"
        },
        "title": {
          "title": "Title",
          "type": "string"
        },
        "body": {
          "title": "Body",
          "type": "string"
        },
        "created_at": {
          "format": "date-time",
          "title": "Created At",
          "type": "string"
        },
        "read_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Read At"
        },
        "tenant_id": {
          "title": "Tenant Id",
          "type": "string"
        },
        "organization_name": {
          "title": "Organization Name",
          "type": "string"
        },
        "target": {
          "$ref": "#/$defs/NotificationTarget"
        },
        "effective_locale": {
          "default": "en-US",
          "title": "Effective Locale",
          "type": "string"
        },
        "locale_origin": {
          "default": "default",
          "enum": [
            "user",
            "organization",
            "installation",
            "default"
          ],
          "title": "Locale Origin",
          "type": "string"
        },
        "powered_by": {
          "const": "Powered by koinon",
          "default": "Powered by koinon",
          "title": "Powered By",
          "type": "string"
        },
        "copyright": {
          "title": "Copyright",
          "type": "string"
        }
      },
      "required": [
        "id",
        "kind",
        "title",
        "body",
        "created_at",
        "read_at",
        "tenant_id",
        "organization_name",
        "target"
      ],
      "title": "OwnNotification",
      "type": "object"
    }
    ```
