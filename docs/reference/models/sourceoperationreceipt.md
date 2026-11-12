<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# SourceOperationReceipt

[All wire models](index.md)

Supporting wire definition. It is not a separate public model alias in the canonical manifest.

Type: [`SourcePolicyReceipt`](sourcepolicyreceipt.md) or [`SourceControlReceipt`](sourcecontrolreceipt.md).


## Model constraints

- Discriminator field: `kind`
- For `"control"`: [`SourceControlReceipt`](sourcecontrolreceipt.md)
- For `"policy"`: [`SourcePolicyReceipt`](sourcepolicyreceipt.md)

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "discriminator": {
        "mapping": {
          "control": "#/$defs/SourceControlReceipt",
          "policy": "#/$defs/SourcePolicyReceipt"
        },
        "propertyName": "kind"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/SourcePolicyReceipt"
        },
        {
          "$ref": "#/$defs/SourceControlReceipt"
        }
      ]
    }
    ```
