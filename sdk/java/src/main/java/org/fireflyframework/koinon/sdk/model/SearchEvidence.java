// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

public record SearchEvidence(String id, String runId, SearchResponse data)
    implements EvidenceResult {
  @Override
  public EvidenceKind kind() {
    return EvidenceKind.SEARCH;
  }
}
