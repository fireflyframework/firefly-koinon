<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# HealthComponent

[All wire models](index.md)

Model aliases: `HealthComponent`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `id` | `string` | Yes | Not specified |
| `configured` | `boolean` | Yes | Not specified |
| `status` | `string` | Yes | Not specified |
| `basis` | `string` | Yes | Not specified |
| `freshness` | `string` | Yes | Not specified |
| `observed_at` | `string` or `null` | No | `null` |
| `expires_at` | `string` or `null` | No | `null` |
| `reason` | `string` | Yes | Not specified |
| `remediation` | `string` | Yes | Not specified |
| `counts` | [`HealthCounts`](healthcounts.md) or `null` | No | `null` |
| `coverage` | `string` | Yes | Not specified |

## Model constraints

- Additional properties: permitted

## Field constraints

### id

- Allowed values: `"database-primary"`, `"database-documents"`, `"database-documents-control"`, `"database-structured"`, `"database-structured-control"`, `"storage-documents"`, `"storage-structured"`, `"indexes-documents"`, `"indexes-structured"`, `"ingestion-documents"`, `"ingestion-structured"`, `"model-configuration"`, `"communications"`, `"workers"`

### status

- Allowed values: `"passed"`, `"failed"`, `"unknown"`, `"disabled"`

### basis

- Allowed values: `"observed"`, `"configuration"`, `"none"`

### freshness

- Allowed values: `"current"`, `"stale"`, `"unknown"`

### observed_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### expires_at

- anyOf branch 1 (`string`): Format: `"date-time"`

### reason

- Allowed values: `"DATABASE_OK"`, `"DATABASE_UNAVAILABLE"`, `"RUNTIME_ROLE_UNVERIFIED"`, `"RUNTIME_ROLE_UNSAFE"`, `"MODULE_DISABLED"`, `"STORAGE_NOT_PROBED"`, `"INDEXES_VERIFIED"`, `"INDEXES_INCOMPLETE"`, `"INDEXES_NOT_PROBED"`, `"NO_INDEXES"`, `"INGESTION_STATE_OBSERVED"`, `"INGESTION_FAILURES"`, `"MODEL_CONFIGURATION_PRESENT"`, `"MODEL_CONFIGURATION_INCOMPLETE"`, `"PROVIDER_NOT_PROBED"`, `"COMMUNICATIONS_DISABLED"`, `"COMMUNICATIONS_CONFIGURED"`, `"COMMUNICATIONS_INCOMPLETE"`, `"WORKER_LIVENESS_UNKNOWN"`, `"OBSERVATION_UNAVAILABLE"`, `"OBSERVATION_BOUNDED"`, `"OBSERVATION_STALE"`

### remediation

- Allowed values: `"none"`, `"retry_read"`, `"review_configuration"`, `"review_indexes"`, `"review_ingestion"`, `"review_communications"`, `"review_worker"`

### coverage

- Allowed values: `"complete"`, `"partial"`, `"unavailable"`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": true,
      "properties": {
        "id": {
          "enum": [
            "database-primary",
            "database-documents",
            "database-documents-control",
            "database-structured",
            "database-structured-control",
            "storage-documents",
            "storage-structured",
            "indexes-documents",
            "indexes-structured",
            "ingestion-documents",
            "ingestion-structured",
            "model-configuration",
            "communications",
            "workers"
          ],
          "title": "Id",
          "type": "string"
        },
        "configured": {
          "title": "Configured",
          "type": "boolean"
        },
        "status": {
          "enum": [
            "passed",
            "failed",
            "unknown",
            "disabled"
          ],
          "title": "Status",
          "type": "string"
        },
        "basis": {
          "enum": [
            "observed",
            "configuration",
            "none"
          ],
          "title": "Basis",
          "type": "string"
        },
        "freshness": {
          "enum": [
            "current",
            "stale",
            "unknown"
          ],
          "title": "Freshness",
          "type": "string"
        },
        "observed_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Observed At"
        },
        "expires_at": {
          "anyOf": [
            {
              "format": "date-time",
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Expires At"
        },
        "reason": {
          "enum": [
            "DATABASE_OK",
            "DATABASE_UNAVAILABLE",
            "RUNTIME_ROLE_UNVERIFIED",
            "RUNTIME_ROLE_UNSAFE",
            "MODULE_DISABLED",
            "STORAGE_NOT_PROBED",
            "INDEXES_VERIFIED",
            "INDEXES_INCOMPLETE",
            "INDEXES_NOT_PROBED",
            "NO_INDEXES",
            "INGESTION_STATE_OBSERVED",
            "INGESTION_FAILURES",
            "MODEL_CONFIGURATION_PRESENT",
            "MODEL_CONFIGURATION_INCOMPLETE",
            "PROVIDER_NOT_PROBED",
            "COMMUNICATIONS_DISABLED",
            "COMMUNICATIONS_CONFIGURED",
            "COMMUNICATIONS_INCOMPLETE",
            "WORKER_LIVENESS_UNKNOWN",
            "OBSERVATION_UNAVAILABLE",
            "OBSERVATION_BOUNDED",
            "OBSERVATION_STALE"
          ],
          "title": "Reason",
          "type": "string"
        },
        "remediation": {
          "enum": [
            "none",
            "retry_read",
            "review_configuration",
            "review_indexes",
            "review_ingestion",
            "review_communications",
            "review_worker"
          ],
          "title": "Remediation",
          "type": "string"
        },
        "counts": {
          "anyOf": [
            {
              "$ref": "#/$defs/HealthCounts"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "coverage": {
          "enum": [
            "complete",
            "partial",
            "unavailable"
          ],
          "title": "Coverage",
          "type": "string"
        }
      },
      "required": [
        "id",
        "configured",
        "status",
        "basis",
        "freshness",
        "reason",
        "remediation",
        "coverage"
      ],
      "title": "HealthComponent",
      "type": "object"
    }
    ```
