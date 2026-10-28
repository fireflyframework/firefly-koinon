// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

public record CatalogProposalEvidence(String id, String runId, CatalogProposal data) implements EvidenceResult {
  @Override public EvidenceKind kind() { return EvidenceKind.PROPOSAL; }
}
