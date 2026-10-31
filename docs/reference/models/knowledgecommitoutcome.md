<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# KnowledgeCommitOutcome

[All wire models](index.md)

Model aliases: `KnowledgeCommitOutcome`.

Type: [`CommittedKnowledge`](committedknowledge.md) or [`PendingKnowledgeCommit`](pendingknowledgecommit.md).


## Model constraints

- Discriminator field: `status`
- For `"committed"`: [`CommittedKnowledge`](committedknowledge.md)
- For `"pending"`: [`PendingKnowledgeCommit`](pendingknowledgecommit.md)

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "discriminator": {
        "mapping": {
          "committed": "#/$defs/CommittedKnowledge",
          "pending": "#/$defs/PendingKnowledgeCommit"
        },
        "propertyName": "status"
      },
      "oneOf": [
        {
          "$ref": "#/$defs/CommittedKnowledge"
        },
        {
          "$ref": "#/$defs/PendingKnowledgeCommit"
        }
      ]
    }
    ```
