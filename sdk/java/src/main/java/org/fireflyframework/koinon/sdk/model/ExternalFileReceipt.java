// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ExternalFileReceipt contract. */
public record ExternalFileReceipt(
    @JsonProperty("source") ExternalFileCatalogEntry source,
    @JsonProperty("assets") List<ExternalFileCatalogEntry> assets
) {
    public ExternalFileReceipt {
        assets=assets==null?null:List.copyOf(assets);
    }

}
