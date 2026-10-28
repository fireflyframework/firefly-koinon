// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical CatalogProposalPatch contract. */
public record CatalogProposalPatch(
    @JsonProperty("name") JsonField<String> name,
    @JsonProperty("description") JsonField<String> description
) {

    public static CatalogProposalPatch empty(){return new CatalogProposalPatch(null,null);}
    public CatalogProposalPatch withName(String value){return new CatalogProposalPatch(JsonField.of(value),description);}
    public CatalogProposalPatch clearName(){return new CatalogProposalPatch(JsonField.clear(),description);}
    public CatalogProposalPatch omitName(){return new CatalogProposalPatch(null,description);}
    public CatalogProposalPatch withDescription(String value){return new CatalogProposalPatch(name,JsonField.of(value));}
    public CatalogProposalPatch clearDescription(){return new CatalogProposalPatch(name,JsonField.clear());}
    public CatalogProposalPatch omitDescription(){return new CatalogProposalPatch(name,null);}
}
