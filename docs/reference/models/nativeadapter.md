<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# NativeAdapter

[All wire models](index.md)

Model aliases: `NativeAdapter`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `ownership` | `string` | Yes | Not specified |
| `read_only` | `boolean` | Yes | Not specified |
| `model_class` | `string` | Yes | Not specified |
| `provider_identity` | `string` | Yes | Not specified |
| `profile_status` | `string` | Yes | Not specified |
| `reason` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### ownership

- Exact value: `"deployment"`

### read_only

- Exact value: `true`

### profile_status

- Exact value: `"unverified"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "ownership": {
          "const": "deployment",
          "title": "Ownership",
          "type": "string"
        },
        "read_only": {
          "const": true,
          "title": "Read Only",
          "type": "boolean"
        },
        "model_class": {
          "title": "Model Class",
          "type": "string"
        },
        "provider_identity": {
          "title": "Provider Identity",
          "type": "string"
        },
        "profile_status": {
          "const": "unverified",
          "title": "Profile Status",
          "type": "string"
        },
        "reason": {
          "title": "Reason",
          "type": "string"
        }
      },
      "required": [
        "ownership",
        "read_only",
        "model_class",
        "provider_identity",
        "profile_status",
        "reason"
      ],
      "title": "NativeAdapter",
      "type": "object"
    }
    ```
