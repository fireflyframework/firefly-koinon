// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ReaderSelectionOutput contract. */
public record ReaderSelectionOutput(
    @JsonProperty("revision") Long revision,
    @JsonProperty("connections") List<ReaderSourceSelection> connections
) {
    public ReaderSelectionOutput {
        connections=connections==null?null:List.copyOf(connections);
    }

}
