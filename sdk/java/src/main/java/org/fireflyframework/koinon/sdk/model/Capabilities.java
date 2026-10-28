// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;



/** Typed canonical Capabilities contract. */
public record Capabilities(
    @JsonProperty("attachments") AttachmentCapabilities attachments,
    @JsonProperty("catalog") CatalogCapability catalog,
    @JsonProperty("agentic") AgenticCapability agentic,
    @JsonProperty("domains") Map<String,DomainCapability> domains,
    @JsonProperty("providers") List<ProviderCapability> providers,
    @JsonProperty("features") List<FeatureCapability> features
) {
    public Capabilities {
        domains=domains==null?null:Map.copyOf(domains);
        providers=providers==null?null:List.copyOf(providers);
        features=features==null?null:List.copyOf(features);
    }

}
