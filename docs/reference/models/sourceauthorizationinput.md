<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceAuthorizationInput

[All wire models](index.md)

Model aliases: `SourceAuthorizationInput`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `provider` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### provider

- Allowed values: `"sharepoint"`, `"onedrive"`, `"google_drive"`


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
        }
      },
      "required": [
        "provider"
      ],
      "title": "SourceAuthorizationInput",
      "type": "object"
    }
    ```
