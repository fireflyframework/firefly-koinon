<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourcePolicyReceipt

[All wire models](index.md)

Model aliases: `SourcePolicyReceipt`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `kind` | `string` | No | `"policy"` |
| `receipt` | [`SourcePolicyOperationOutput`](sourcepolicyoperationoutput.md) | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### kind

- Exact value: `"policy"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "kind": {
          "const": "policy",
          "default": "policy",
          "title": "Kind",
          "type": "string"
        },
        "receipt": {
          "$ref": "#/$defs/SourcePolicyOperationOutput"
        }
      },
      "required": [
        "receipt"
      ],
      "title": "SourcePolicyReceipt",
      "type": "object"
    }
    ```
