// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ProductHelpContext contract. */
public record ProductHelpContext(
    @JsonProperty("kind") ProductHelpContextKind kind,
    @JsonProperty("product_name") String productName,
    @JsonProperty("assistant_name") String assistantName,
    @JsonProperty("branding_revision") Long brandingRevision,
    @JsonProperty("branding_origin") KnowledgeSettingsOrigin brandingOrigin,
    @JsonProperty("selection") ProductHelpContextSelection selection,
    @JsonProperty("tools") List<ProductHelpContextTools> tools
) {
    public ProductHelpContext {
        tools=tools==null?null:List.copyOf(tools);
    }

}
