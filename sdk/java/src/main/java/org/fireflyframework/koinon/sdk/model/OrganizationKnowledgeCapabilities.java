// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationKnowledgeCapabilities contract. */
public record OrganizationKnowledgeCapabilities(
    @JsonProperty("documents") DocumentKnowledgeCapabilities documents,
    @JsonProperty("structured") StructuredKnowledgeCapabilities structured
) {

    public static OrganizationKnowledgeCapabilities empty(){return new OrganizationKnowledgeCapabilities(null,null);}
    public OrganizationKnowledgeCapabilities withDocuments(DocumentKnowledgeCapabilities value){return new OrganizationKnowledgeCapabilities(value,structured);}
    public OrganizationKnowledgeCapabilities withStructured(StructuredKnowledgeCapabilities value){return new OrganizationKnowledgeCapabilities(documents,value);}
}
