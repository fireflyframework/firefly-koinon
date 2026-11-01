<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# EmailPreview

[All wire models](index.md)

Model aliases: `EmailPreview`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `subject` | `string` | Yes | Not specified |
| `sender_name` | `string` | Yes | Not specified |
| `recipient_display_name` | `string` | Yes | Not specified |
| `recipient_email` | `string` | Yes | Not specified |
| `heading` | `string` | Yes | Not specified |
| `paragraphs` | Array of `string` | Yes | Not specified |
| `action_label` | `string` | Yes | Not specified |
| `footer` | `string` | Yes | Not specified |
| `product_name` | `string` | Yes | Not specified |
| `accent_color` | `string` | Yes | Not specified |
| `branding` | [`BrandingValues`](brandingvalues.md) | Yes | Not specified |
| `rendered_html` | `string` | No | `""` |
| `rendered_text` | `string` | No | `""` |
| `usage_summary` | [`CommunicationUsageSummary`](communicationusagesummary.md) or `null` | No | `null` |
| `activity_summary` | [`ActivitySummary`](activitysummary.md) or `null` | No | `null` |
| `organization_name` | `string` | No | `""` |
| `workspace_name` | `string` or `null` | No | `null` |
| `effective_locale` | `string` | No | `"en-US"` |
| `locale_origin` | `string` | No | `"default"` |
| `powered_by` | `string` | No | `"Powered by koinon"` |
| `copyright` | `string` | No | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

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
        "subject": {
          "title": "Subject",
          "type": "string"
        },
        "sender_name": {
          "title": "Sender Name",
          "type": "string"
        },
        "recipient_display_name": {
          "title": "Recipient Display Name",
          "type": "string"
        },
        "recipient_email": {
          "title": "Recipient Email",
          "type": "string"
        },
        "heading": {
          "title": "Heading",
          "type": "string"
        },
        "paragraphs": {
          "items": {
            "type": "string"
          },
          "title": "Paragraphs",
          "type": "array"
        },
        "action_label": {
          "title": "Action Label",
          "type": "string"
        },
        "footer": {
          "title": "Footer",
          "type": "string"
        },
        "product_name": {
          "title": "Product Name",
          "type": "string"
        },
        "accent_color": {
          "title": "Accent Color",
          "type": "string"
        },
        "branding": {
          "$ref": "#/$defs/BrandingValues"
        },
        "rendered_html": {
          "default": "",
          "title": "Rendered Html",
          "type": "string"
        },
        "rendered_text": {
          "default": "",
          "title": "Rendered Text",
          "type": "string"
        },
        "usage_summary": {
          "anyOf": [
            {
              "$ref": "#/$defs/CommunicationUsageSummary"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "activity_summary": {
          "anyOf": [
            {
              "$ref": "#/$defs/ActivitySummary"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "organization_name": {
          "default": "",
          "title": "Organization Name",
          "type": "string"
        },
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
        "subject",
        "sender_name",
        "recipient_display_name",
        "recipient_email",
        "heading",
        "paragraphs",
        "action_label",
        "footer",
        "product_name",
        "accent_color",
        "branding"
      ],
      "title": "EmailPreview",
      "type": "object"
    }
    ```
