<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# OrganizationKnowledgeCapabilities

[All wire models](index.md)

Model aliases: `OrganizationKnowledgeCapabilities`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `documents` | [`DocumentKnowledgeCapabilities`](documentknowledgecapabilities.md) | Yes | Not specified |
| `structured` | [`StructuredKnowledgeCapabilities`](structuredknowledgecapabilities.md) | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "documents": {
          "$ref": "#/$defs/DocumentKnowledgeCapabilities"
        },
        "structured": {
          "$ref": "#/$defs/StructuredKnowledgeCapabilities"
        }
      },
      "required": [
        "documents",
        "structured"
      ],
      "title": "OrganizationKnowledgeCapabilities",
      "type": "object"
    }
    ```
