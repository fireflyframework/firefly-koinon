// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical EvidenceManifest contract. */
public record EvidenceManifest(
    @JsonProperty("revision") String revision,
    @JsonProperty("sources") List<SourceReference> sources,
    @JsonProperty("complete") Boolean complete,
    @JsonProperty("omissions") List<String> omissions
) {
    public EvidenceManifest {
        sources=sources==null?null:List.copyOf(sources);
        omissions=omissions==null?null:List.copyOf(omissions);
    }

}
