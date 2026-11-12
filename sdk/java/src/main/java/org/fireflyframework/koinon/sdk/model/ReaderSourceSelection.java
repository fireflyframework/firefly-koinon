// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ReaderSourceSelection contract. */
public record ReaderSourceSelection(
    @JsonProperty("provider") ReaderSourceSelectionProvider provider,
    @JsonProperty("external_tenant") JsonField<String> externalTenant,
    @JsonProperty("connection_id") String connectionId
) {

    public static ReaderSourceSelection empty(){return new ReaderSourceSelection(null,null,null);}
    public ReaderSourceSelection withProvider(ReaderSourceSelectionProvider value){return new ReaderSourceSelection(value,externalTenant,connectionId);}
    public ReaderSourceSelection withExternalTenant(String value){return new ReaderSourceSelection(provider,JsonField.of(value),connectionId);}
    public ReaderSourceSelection clearExternalTenant(){return new ReaderSourceSelection(provider,JsonField.clear(),connectionId);}
    public ReaderSourceSelection omitExternalTenant(){return new ReaderSourceSelection(provider,null,connectionId);}
    public ReaderSourceSelection withConnectionId(String value){return new ReaderSourceSelection(provider,externalTenant,value);}
}
