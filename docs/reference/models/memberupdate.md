<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MemberUpdate

[All wire models](index.md)

Model aliases: `MemberUpdate`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `role` | `string` or `null` | No | `null` |
| `active` | `boolean` or `null` | No | `null` |

## Model constraints

- Additional properties: not permitted

## Field constraints

### role

- anyOf branch 1 (`string`): Allowed values: `"viewer"`, `"analyst"`, `"editor"`, `"operator"`, `"admin"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "role": {
          "anyOf": [
            {
              "enum": [
                "viewer",
                "analyst",
                "editor",
                "operator",
                "admin"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Role"
        },
        "active": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Active"
        }
      },
      "title": "MemberUpdate",
      "type": "object"
    }
    ```
