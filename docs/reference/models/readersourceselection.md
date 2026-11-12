<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ReaderSourceSelection

[All wire models](index.md)

Model aliases: `ReaderSourceSelection`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `provider` | `string` | Yes | Not specified |
| `external_tenant` | `string` or `null` | No | `null` |
| `connection_id` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### provider

- Allowed values: `"sharepoint"`, `"onedrive"`, `"google_drive"`

### external_tenant

- anyOf branch 1 (`string`): Minimum length: `1`
- anyOf branch 1 (`string`): Maximum length: `1024`

### connection_id

- Minimum length: `1`
- Maximum length: `64`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
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
        "external_tenant": {
          "anyOf": [
            {
              "maxLength": 1024,
              "minLength": 1,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "External Tenant"
        },
        "connection_id": {
          "maxLength": 64,
          "minLength": 1,
          "title": "Connection Id",
          "type": "string"
        }
      },
      "required": [
        "provider",
        "connection_id"
      ],
      "title": "ReaderSourceSelection",
      "type": "object"
    }
    ```
