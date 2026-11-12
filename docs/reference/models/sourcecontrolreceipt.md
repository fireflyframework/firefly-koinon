<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceControlReceipt

[All wire models](index.md)

Model aliases: `SourceControlReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | No | `"control"` |
| `receipt` | [`SourceControlOutput`](sourcecontroloutput.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Exact value: `"control"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "kind": {
          "const": "control",
          "default": "control",
          "title": "Kind",
          "type": "string"
        },
        "receipt": {
          "$ref": "#/$defs/SourceControlOutput"
        }
      },
      "required": [
        "receipt"
      ],
      "title": "SourceControlReceipt",
      "type": "object"
    }
    ```
