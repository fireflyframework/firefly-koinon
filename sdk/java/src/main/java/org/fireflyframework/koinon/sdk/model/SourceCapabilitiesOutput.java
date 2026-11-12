// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceCapabilitiesOutput contract. */
public record SourceCapabilitiesOutput(
    @JsonProperty("accounts_available") Boolean accountsAvailable,
    @JsonProperty("inbound_only") Boolean inboundOnly,
    @JsonProperty("synchronization_available") Boolean synchronizationAvailable,
    @JsonProperty("providers") List<SourceProviderCapability> providers,
    @JsonProperty("modes") List<AddKnowledgeMode> modes,
    @JsonProperty("formats") List<SourceFormatCapability> formats,
    @JsonProperty("schedule") SourceScheduleCapability schedule
) {
    public SourceCapabilitiesOutput {
        providers=providers==null?null:List.copyOf(providers);
        modes=modes==null?null:List.copyOf(modes);
        formats=formats==null?null:List.copyOf(formats);
    }

}
