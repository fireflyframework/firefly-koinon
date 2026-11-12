// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ReaderSelectionInput contract. */
public record ReaderSelectionInput(
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("operation_id") String operationId,
    @JsonProperty("connections") List<ReaderSourceSelection> connections
) {
    public ReaderSelectionInput {
        connections=connections==null?null:List.copyOf(connections);
    }

    public static ReaderSelectionInput empty(){return new ReaderSelectionInput(null,null,null);}
    public ReaderSelectionInput withExpectedRevision(Long value){return new ReaderSelectionInput(value,operationId,connections);}
    public ReaderSelectionInput withOperationId(String value){return new ReaderSelectionInput(expectedRevision,value,connections);}
    public ReaderSelectionInput withConnections(List<ReaderSourceSelection> value){return new ReaderSelectionInput(expectedRevision,operationId,value);}
}
