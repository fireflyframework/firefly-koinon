// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;



/** Typed canonical AttachmentPromotionView contract. */
public record AttachmentPromotionView(
    @JsonProperty("promotion_id") String promotionId,
    @JsonProperty("attachment_id") String attachmentId,
    @JsonProperty("action") AttachmentPromotionViewAction action,
    @JsonProperty("source") PromotedCatalogEntry source,
    @JsonProperty("assets") List<PromotedCatalogEntry> assets,
    @JsonProperty("asset") PromotedCatalogEntry asset,
    @JsonProperty("table") PromotedCatalogEntry table,
    @JsonProperty("version") PromotedCatalogEntry version,
    @JsonProperty("effects") JsonNode effects
) {
    public AttachmentPromotionView {
        assets=assets==null?null:List.copyOf(assets);
        effects=ModelValues.json(effects);
    }
    @Override public JsonNode effects(){return ModelValues.json(effects);}
}
