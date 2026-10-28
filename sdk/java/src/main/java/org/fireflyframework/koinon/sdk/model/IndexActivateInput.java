// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IndexActivateInput contract. */
public record IndexActivateInput(
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("expected_active_id") JsonField<String> expectedActiveId,
    @JsonProperty("expected_connection_revision") JsonField<Long> expectedConnectionRevision,
    @JsonProperty("recovery") JsonField<IndexActivateInputRecovery> recovery
) {

    public static IndexActivateInput empty(){return new IndexActivateInput(null,null,null,null);}
    public IndexActivateInput withExpectedRevision(Long value){return new IndexActivateInput(value,expectedActiveId,expectedConnectionRevision,recovery);}
    public IndexActivateInput withExpectedActiveId(String value){return new IndexActivateInput(expectedRevision,JsonField.of(value),expectedConnectionRevision,recovery);}
    public IndexActivateInput clearExpectedActiveId(){return new IndexActivateInput(expectedRevision,JsonField.clear(),expectedConnectionRevision,recovery);}
    public IndexActivateInput omitExpectedActiveId(){return new IndexActivateInput(expectedRevision,null,expectedConnectionRevision,recovery);}
    public IndexActivateInput withExpectedConnectionRevision(Long value){return new IndexActivateInput(expectedRevision,expectedActiveId,JsonField.of(value),recovery);}
    public IndexActivateInput clearExpectedConnectionRevision(){return new IndexActivateInput(expectedRevision,expectedActiveId,JsonField.clear(),recovery);}
    public IndexActivateInput omitExpectedConnectionRevision(){return new IndexActivateInput(expectedRevision,expectedActiveId,null,recovery);}
    public IndexActivateInput withRecovery(IndexActivateInputRecovery value){return new IndexActivateInput(expectedRevision,expectedActiveId,expectedConnectionRevision,JsonField.of(value));}
    public IndexActivateInput clearRecovery(){return new IndexActivateInput(expectedRevision,expectedActiveId,expectedConnectionRevision,JsonField.clear());}
    public IndexActivateInput omitRecovery(){return new IndexActivateInput(expectedRevision,expectedActiveId,expectedConnectionRevision,null);}
}
