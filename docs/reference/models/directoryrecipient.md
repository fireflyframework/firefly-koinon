<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DirectoryRecipient

[All wire models](index.md)

Model aliases: `DirectoryRecipient`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `recipient_ref` | `string` or `null` | Yes | Not specified |
| `display_name` | `string` | Yes | Not specified |
| `email` | `string` or `null` | Yes | Not specified |
| `provider_label` | `string` | Yes | Not specified |
| `delivery_address_status` | `string` | Yes | Not specified |
| `eligibility` | `string` | Yes | Not specified |
| `eligibility_reason` | `string` or `null` | No | `null` |

## Model constraints

- Additional properties: permitted

## Field constraints

### delivery_address_status

- Allowed values: `"verified_directory"`, `"missing"`, `"unverified"`, `"unavailable"`

### eligibility

- Allowed values: `"eligible"`, `"already_has_access"`, `"unavailable"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "recipient_ref": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Recipient Ref"
        },
        "display_name": {
          "title": "Display Name",
          "type": "string"
        },
        "email": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Email"
        },
        "provider_label": {
          "title": "Provider Label",
          "type": "string"
        },
        "delivery_address_status": {
          "enum": [
            "verified_directory",
            "missing",
            "unverified",
            "unavailable"
          ],
          "title": "Delivery Address Status",
          "type": "string"
        },
        "eligibility": {
          "enum": [
            "eligible",
            "already_has_access",
            "unavailable"
          ],
          "title": "Eligibility",
          "type": "string"
        },
        "eligibility_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Eligibility Reason"
        }
      },
      "required": [
        "recipient_ref",
        "display_name",
        "email",
        "provider_label",
        "delivery_address_status",
        "eligibility"
      ],
      "title": "DirectoryRecipient",
      "type": "object"
    }
    ```
