// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical AgentInput contract. */
public record AgentInput(
    @JsonProperty("model_options") JsonField<ModelParameters> modelOptions,
    @JsonProperty("name") JsonField<String> name,
    @JsonProperty("description") JsonField<String> description,
    @JsonProperty("provider_id") JsonField<String> providerId,
    @JsonProperty("model_id") JsonField<String> modelId,
    @JsonProperty("tools") JsonField<List<AgentTool>> tools,
    @JsonProperty("scope") JsonField<KnowledgeScope> scope,
    @JsonProperty("instructions") JsonField<String> instructions,
    @JsonProperty("enabled") JsonField<Boolean> enabled
) {

    public static AgentInput empty(){return new AgentInput(null,null,null,null,null,null,null,null,null);}
    public AgentInput withModelOptions(ModelParameters value){return new AgentInput(JsonField.of(value),name,description,providerId,modelId,tools,scope,instructions,enabled);}
    public AgentInput clearModelOptions(){return new AgentInput(JsonField.clear(),name,description,providerId,modelId,tools,scope,instructions,enabled);}
    public AgentInput omitModelOptions(){return new AgentInput(null,name,description,providerId,modelId,tools,scope,instructions,enabled);}
    public AgentInput withName(String value){return new AgentInput(modelOptions,JsonField.of(value),description,providerId,modelId,tools,scope,instructions,enabled);}
    public AgentInput clearName(){return new AgentInput(modelOptions,JsonField.clear(),description,providerId,modelId,tools,scope,instructions,enabled);}
    public AgentInput omitName(){return new AgentInput(modelOptions,null,description,providerId,modelId,tools,scope,instructions,enabled);}
    public AgentInput withDescription(String value){return new AgentInput(modelOptions,name,JsonField.of(value),providerId,modelId,tools,scope,instructions,enabled);}
    public AgentInput clearDescription(){return new AgentInput(modelOptions,name,JsonField.clear(),providerId,modelId,tools,scope,instructions,enabled);}
    public AgentInput omitDescription(){return new AgentInput(modelOptions,name,null,providerId,modelId,tools,scope,instructions,enabled);}
    public AgentInput withProviderId(String value){return new AgentInput(modelOptions,name,description,JsonField.of(value),modelId,tools,scope,instructions,enabled);}
    public AgentInput clearProviderId(){return new AgentInput(modelOptions,name,description,JsonField.clear(),modelId,tools,scope,instructions,enabled);}
    public AgentInput omitProviderId(){return new AgentInput(modelOptions,name,description,null,modelId,tools,scope,instructions,enabled);}
    public AgentInput withModelId(String value){return new AgentInput(modelOptions,name,description,providerId,JsonField.of(value),tools,scope,instructions,enabled);}
    public AgentInput clearModelId(){return new AgentInput(modelOptions,name,description,providerId,JsonField.clear(),tools,scope,instructions,enabled);}
    public AgentInput omitModelId(){return new AgentInput(modelOptions,name,description,providerId,null,tools,scope,instructions,enabled);}
    public AgentInput withTools(List<AgentTool> value){return new AgentInput(modelOptions,name,description,providerId,modelId,JsonField.of(value),scope,instructions,enabled);}
    public AgentInput clearTools(){return new AgentInput(modelOptions,name,description,providerId,modelId,JsonField.clear(),scope,instructions,enabled);}
    public AgentInput omitTools(){return new AgentInput(modelOptions,name,description,providerId,modelId,null,scope,instructions,enabled);}
    public AgentInput withScope(KnowledgeScope value){return new AgentInput(modelOptions,name,description,providerId,modelId,tools,JsonField.of(value),instructions,enabled);}
    public AgentInput clearScope(){return new AgentInput(modelOptions,name,description,providerId,modelId,tools,JsonField.clear(),instructions,enabled);}
    public AgentInput omitScope(){return new AgentInput(modelOptions,name,description,providerId,modelId,tools,null,instructions,enabled);}
    public AgentInput withInstructions(String value){return new AgentInput(modelOptions,name,description,providerId,modelId,tools,scope,JsonField.of(value),enabled);}
    public AgentInput clearInstructions(){return new AgentInput(modelOptions,name,description,providerId,modelId,tools,scope,JsonField.clear(),enabled);}
    public AgentInput omitInstructions(){return new AgentInput(modelOptions,name,description,providerId,modelId,tools,scope,null,enabled);}
    public AgentInput withEnabled(Boolean value){return new AgentInput(modelOptions,name,description,providerId,modelId,tools,scope,instructions,JsonField.of(value));}
    public AgentInput clearEnabled(){return new AgentInput(modelOptions,name,description,providerId,modelId,tools,scope,instructions,JsonField.clear());}
    public AgentInput omitEnabled(){return new AgentInput(modelOptions,name,description,providerId,modelId,tools,scope,instructions,null);}
}
