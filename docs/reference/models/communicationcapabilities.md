<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# CommunicationCapabilities

[All wire models](index.md)

Model aliases: `CommunicationCapabilities`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `state` | `string` | Yes | Not specified |
| `provider_label` | `string` | Yes | Not specified |
| `sender_name` | `string` | Yes | Not specified |
| `sender_address` | `string` | Yes | Not specified |
| `reply_to` | `string` or `null` | No | `null` |
| `sender_options` | Array of [`VerifiedSenderOption`](verifiedsenderoption.md) | Yes | Not specified |
| `public_address_configured` | `boolean` | Yes | Not specified |
| `public_url` | `string` or `null` | Yes | Not specified |
| `acceptance_base` | `string` or `null` | Yes | Not specified |
| `issues` | Array of [`CommunicationIssue`](communicationissue.md) | Yes | Not specified |
| `effective_locale` | `string` | No | `"en-US"` |
| `locale_origin` | `string` | No | `"default"` |

## Model constraints

- Additional properties: permitted

## Field constraints

### state

- Allowed values: `"disabled"`, `"not_configured"`, `"ready"`, `"degraded"`

### locale_origin

- Allowed values: `"user"`, `"organization"`, `"installation"`, `"default"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "state": {
          "enum": [
            "disabled",
            "not_configured",
            "ready",
            "degraded"
          ],
          "title": "State",
          "type": "string"
        },
        "provider_label": {
          "title": "Provider Label",
          "type": "string"
        },
        "sender_name": {
          "title": "Sender Name",
          "type": "string"
        },
        "sender_address": {
          "title": "Sender Address",
          "type": "string"
        },
        "reply_to": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Reply To"
        },
        "sender_options": {
          "items": {
            "$ref": "#/$defs/VerifiedSenderOption"
          },
          "title": "Sender Options",
          "type": "array"
        },
        "public_address_configured": {
          "title": "Public Address Configured",
          "type": "boolean"
        },
        "public_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Public Url"
        },
        "acceptance_base": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Acceptance Base"
        },
        "issues": {
          "items": {
            "$ref": "#/$defs/CommunicationIssue"
          },
          "title": "Issues",
          "type": "array"
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
        }
      },
      "required": [
        "state",
        "provider_label",
        "sender_name",
        "sender_address",
        "sender_options",
        "public_address_configured",
        "public_url",
        "acceptance_base",
        "issues"
      ],
      "title": "CommunicationCapabilities",
      "type": "object"
    }
    ```
