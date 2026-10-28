// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

public record SchemaEvidence(String id, String runId, DatasetSchema data)
    implements EvidenceResult {
  @Override
  public EvidenceKind kind() {
    return EvidenceKind.SCHEMA;
  }
}
