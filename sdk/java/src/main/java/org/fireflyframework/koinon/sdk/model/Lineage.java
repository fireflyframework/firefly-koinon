// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical Lineage contract. */
public record Lineage(
    @JsonProperty("nodes") List<LineageNode> nodes,
    @JsonProperty("edges") List<LineageEdge> edges
) {
    public Lineage {
        nodes=nodes==null?null:List.copyOf(nodes);
        edges=edges==null?null:List.copyOf(edges);
    }

}
