<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AttachmentProgress

[All wire models](index.md)

Model aliases: `AttachmentProgress`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `status` | `string` | Yes | Not specified |
| `percent` | `integer` | Yes | Not specified |
| `attempts` | `integer` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### status

- Allowed values: `"storing"`, `"queued"`, `"running"`, `"succeeded"`, `"failed"`, `"cancelled"`

### percent

- Minimum: `0`
- Maximum: `100`

### attempts

- Minimum: `0`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "status": {
          "enum": [
            "storing",
            "queued",
            "running",
            "succeeded",
            "failed",
            "cancelled"
          ],
          "title": "Status",
          "type": "string"
        },
        "percent": {
          "maximum": 100,
          "minimum": 0,
          "title": "Percent",
          "type": "integer"
        },
        "attempts": {
          "minimum": 0,
          "title": "Attempts",
          "type": "integer"
        }
      },
      "required": [
        "status",
        "percent",
        "attempts"
      ],
      "title": "AttachmentProgress",
      "type": "object"
    }
    ```
