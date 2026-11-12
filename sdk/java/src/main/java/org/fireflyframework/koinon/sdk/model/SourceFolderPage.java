// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceFolderPage contract. */
public record SourceFolderPage(
    @JsonProperty("folder") SourceItemOutput folder,
    @JsonProperty("items") List<SourceItemOutput> items,
    @JsonProperty("next_cursor") String nextCursor
) {
    public SourceFolderPage {
        items=items==null?null:List.copyOf(items);
    }

}
