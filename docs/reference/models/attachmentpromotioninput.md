<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# AttachmentPromotionInput

[All wire models](index.md)

Model aliases: `AttachmentPromotionInput`.

Type: [`AddKnowledge`](addknowledge.md) or [`ReplaceDocument`](replacedocument.md) or [`ReplaceTable`](replacetable.md).


## Model constraints

- Discriminator field: `action`
- For `"add"`: [`AddKnowledge`](addknowledge.md)
- For `"replace_document"`: [`ReplaceDocument`](replacedocument.md)
- For `"replace_table"`: [`ReplaceTable`](replacetable.md)

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "discriminator": {
        "mapping": {
          "add": "#/$defs/AddKnowledge",
          "replace_document": "#/$defs/ReplaceDocument",
          "replace_table": "#/$defs/ReplaceTable"
        },
        "propertyName": "action"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/AddKnowledge"
        },
        {
          "$ref": "#/$defs/ReplaceDocument"
        },
        {
          "$ref": "#/$defs/ReplaceTable"
        }
      ],
      "title": "AttachmentPromotionInput"
    }
    ```
