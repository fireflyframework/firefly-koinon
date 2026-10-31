// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical DocumentKnowledgeCapabilities contract. */
public record DocumentKnowledgeCapabilities(
    @JsonProperty("answer_modes") List<KnowledgeAnswerMode> answerModes,
    @JsonProperty("rlm_curated_knowledge_supported") Boolean rlmCuratedKnowledgeSupported,
    @JsonProperty("rlm_curated_knowledge_reason") JsonField<DocumentKnowledgeCapabilitiesRlmCuratedKnowledgeReason> rlmCuratedKnowledgeReason,
    @JsonProperty("rlm_model_role") DocumentKnowledgeCapabilitiesRlmModelRole rlmModelRole,
    @JsonProperty("rlm_recorded_views_required") Boolean rlmRecordedViewsRequired,
    @JsonProperty("rlm_recorded_views_reason") DocumentKnowledgeCapabilitiesRlmRecordedViewsReason rlmRecordedViewsReason,
    @JsonProperty("bounds") DocumentKnowledgeBounds bounds
) {
    public DocumentKnowledgeCapabilities {
        answerModes=answerModes==null?null:List.copyOf(answerModes);
    }

    public static DocumentKnowledgeCapabilities empty(){return new DocumentKnowledgeCapabilities(null,null,null,null,null,null,null);}
    public DocumentKnowledgeCapabilities withAnswerModes(List<KnowledgeAnswerMode> value){return new DocumentKnowledgeCapabilities(value,rlmCuratedKnowledgeSupported,rlmCuratedKnowledgeReason,rlmModelRole,rlmRecordedViewsRequired,rlmRecordedViewsReason,bounds);}
    public DocumentKnowledgeCapabilities withRlmCuratedKnowledgeSupported(Boolean value){return new DocumentKnowledgeCapabilities(answerModes,value,rlmCuratedKnowledgeReason,rlmModelRole,rlmRecordedViewsRequired,rlmRecordedViewsReason,bounds);}
    public DocumentKnowledgeCapabilities withRlmCuratedKnowledgeReason(DocumentKnowledgeCapabilitiesRlmCuratedKnowledgeReason value){return new DocumentKnowledgeCapabilities(answerModes,rlmCuratedKnowledgeSupported,JsonField.of(value),rlmModelRole,rlmRecordedViewsRequired,rlmRecordedViewsReason,bounds);}
    public DocumentKnowledgeCapabilities clearRlmCuratedKnowledgeReason(){return new DocumentKnowledgeCapabilities(answerModes,rlmCuratedKnowledgeSupported,JsonField.clear(),rlmModelRole,rlmRecordedViewsRequired,rlmRecordedViewsReason,bounds);}
    public DocumentKnowledgeCapabilities omitRlmCuratedKnowledgeReason(){return new DocumentKnowledgeCapabilities(answerModes,rlmCuratedKnowledgeSupported,null,rlmModelRole,rlmRecordedViewsRequired,rlmRecordedViewsReason,bounds);}
    public DocumentKnowledgeCapabilities withRlmModelRole(DocumentKnowledgeCapabilitiesRlmModelRole value){return new DocumentKnowledgeCapabilities(answerModes,rlmCuratedKnowledgeSupported,rlmCuratedKnowledgeReason,value,rlmRecordedViewsRequired,rlmRecordedViewsReason,bounds);}
    public DocumentKnowledgeCapabilities withRlmRecordedViewsRequired(Boolean value){return new DocumentKnowledgeCapabilities(answerModes,rlmCuratedKnowledgeSupported,rlmCuratedKnowledgeReason,rlmModelRole,value,rlmRecordedViewsReason,bounds);}
    public DocumentKnowledgeCapabilities withRlmRecordedViewsReason(DocumentKnowledgeCapabilitiesRlmRecordedViewsReason value){return new DocumentKnowledgeCapabilities(answerModes,rlmCuratedKnowledgeSupported,rlmCuratedKnowledgeReason,rlmModelRole,rlmRecordedViewsRequired,value,bounds);}
    public DocumentKnowledgeCapabilities withBounds(DocumentKnowledgeBounds value){return new DocumentKnowledgeCapabilities(answerModes,rlmCuratedKnowledgeSupported,rlmCuratedKnowledgeReason,rlmModelRole,rlmRecordedViewsRequired,rlmRecordedViewsReason,value);}
}
