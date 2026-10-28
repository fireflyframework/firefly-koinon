// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;
import java.util.List;



/** Typed canonical ModelParameters contract. */
public record ModelParameters(
    @JsonProperty("max_tokens") Integer maxTokens,
    @JsonProperty("temperature") JsonField<BigDecimal> temperature,
    @JsonProperty("top_p") JsonField<BigDecimal> topP,
    @JsonProperty("top_k") JsonField<Integer> topK,
    @JsonProperty("seed") JsonField<Integer> seed,
    @JsonProperty("stop_sequences") JsonField<List<String>> stopSequences,
    @JsonProperty("request_timeout") JsonField<BigDecimal> requestTimeout,
    @JsonProperty("reasoning") JsonField<ReasoningEffort> reasoning,
    @JsonProperty("reasoning_budget_tokens") JsonField<Integer> reasoningBudgetTokens,
    @JsonProperty("parallel_tool_calls") JsonField<Boolean> parallelToolCalls,
    @JsonProperty("store_responses") JsonField<Boolean> storeResponses,
    @JsonProperty("output_verbosity") JsonField<OutputVerbosity> outputVerbosity
) {

    public static ModelParameters empty(){return new ModelParameters(null,null,null,null,null,null,null,null,null,null,null,null);}
    public ModelParameters withMaxTokens(Integer value){return new ModelParameters(value,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters withTemperature(BigDecimal value){return new ModelParameters(maxTokens,JsonField.of(value),topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters clearTemperature(){return new ModelParameters(maxTokens,JsonField.clear(),topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters omitTemperature(){return new ModelParameters(maxTokens,null,topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters withTopP(BigDecimal value){return new ModelParameters(maxTokens,temperature,JsonField.of(value),topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters clearTopP(){return new ModelParameters(maxTokens,temperature,JsonField.clear(),topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters omitTopP(){return new ModelParameters(maxTokens,temperature,null,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters withTopK(Integer value){return new ModelParameters(maxTokens,temperature,topP,JsonField.of(value),seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters clearTopK(){return new ModelParameters(maxTokens,temperature,topP,JsonField.clear(),seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters omitTopK(){return new ModelParameters(maxTokens,temperature,topP,null,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters withSeed(Integer value){return new ModelParameters(maxTokens,temperature,topP,topK,JsonField.of(value),stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters clearSeed(){return new ModelParameters(maxTokens,temperature,topP,topK,JsonField.clear(),stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters omitSeed(){return new ModelParameters(maxTokens,temperature,topP,topK,null,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters withStopSequences(List<String> value){return new ModelParameters(maxTokens,temperature,topP,topK,seed,JsonField.of(value),requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters clearStopSequences(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,JsonField.clear(),requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters omitStopSequences(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,null,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters withRequestTimeout(BigDecimal value){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,JsonField.of(value),reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters clearRequestTimeout(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,JsonField.clear(),reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters omitRequestTimeout(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,null,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters withReasoning(ReasoningEffort value){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,JsonField.of(value),reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters clearReasoning(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,JsonField.clear(),reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters omitReasoning(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,null,reasoningBudgetTokens,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters withReasoningBudgetTokens(Integer value){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,JsonField.of(value),parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters clearReasoningBudgetTokens(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,JsonField.clear(),parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters omitReasoningBudgetTokens(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,null,parallelToolCalls,storeResponses,outputVerbosity);}
    public ModelParameters withParallelToolCalls(Boolean value){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,JsonField.of(value),storeResponses,outputVerbosity);}
    public ModelParameters clearParallelToolCalls(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,JsonField.clear(),storeResponses,outputVerbosity);}
    public ModelParameters omitParallelToolCalls(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,null,storeResponses,outputVerbosity);}
    public ModelParameters withStoreResponses(Boolean value){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,JsonField.of(value),outputVerbosity);}
    public ModelParameters clearStoreResponses(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,JsonField.clear(),outputVerbosity);}
    public ModelParameters omitStoreResponses(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,null,outputVerbosity);}
    public ModelParameters withOutputVerbosity(OutputVerbosity value){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,JsonField.of(value));}
    public ModelParameters clearOutputVerbosity(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,JsonField.clear());}
    public ModelParameters omitOutputVerbosity(){return new ModelParameters(maxTokens,temperature,topP,topK,seed,stopSequences,requestTimeout,reasoning,reasoningBudgetTokens,parallelToolCalls,storeResponses,null);}
}
