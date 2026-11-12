<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceProviderCapability

[All wire models](index.md)

Model aliases: `SourceProviderCapability`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `provider` | `string` | Yes | Not specified |
| `display_name` | `string` | Yes | Not specified |
| `consent_available` | `boolean` | Yes | Not specified |
| `unavailable_reason` | `string` or `null` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### provider

- Allowed values: `"sharepoint"`, `"onedrive"`, `"google_drive"`

### unavailable_reason

- anyOf branch 1 (`string`): Allowed values: `"disabled"`, `"not_configured"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "provider": {
          "enum": [
            "sharepoint",
            "onedrive",
            "google_drive"
          ],
          "title": "Provider",
          "type": "string"
        },
        "display_name": {
          "title": "Display Name",
          "type": "string"
        },
        "consent_available": {
          "title": "Consent Available",
          "type": "boolean"
        },
        "unavailable_reason": {
          "anyOf": [
            {
              "enum": [
                "disabled",
                "not_configured"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "title": "Unavailable Reason"
        }
      },
      "required": [
        "provider",
        "display_name",
        "consent_available",
        "unavailable_reason"
      ],
      "title": "SourceProviderCapability",
      "type": "object"
    }
    ```
