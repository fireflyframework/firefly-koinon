<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ExportReviewRequest

[All wire models](index.md)

Model aliases: `ExportReviewRequest`.

Type: [`ConversationExportInput`](conversationexportinput.md) or [`QueryResultExportInput`](queryresultexportinput.md).


## Model constraints

- Discriminator field: `kind`
- For `"conversation"`: [`ConversationExportInput`](conversationexportinput.md)
- For `"query_result"`: [`QueryResultExportInput`](queryresultexportinput.md)

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "discriminator": {
        "mapping": {
          "conversation": "#/$defs/ConversationExportInput",
          "query_result": "#/$defs/QueryResultExportInput"
        },
        "propertyName": "kind"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/ConversationExportInput"
        },
        {
          "$ref": "#/$defs/QueryResultExportInput"
        }
      ],
      "title": "ExportReviewRequest"
    }
    ```
