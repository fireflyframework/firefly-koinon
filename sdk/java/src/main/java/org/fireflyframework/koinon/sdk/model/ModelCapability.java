// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ModelCapability contract. */
public record ModelCapability(
    @JsonProperty("image_input") CapabilityState imageInput,
    @JsonProperty("audio_input") CapabilityState audioInput,
    @JsonProperty("option_fields") List<String> optionFields,
    @JsonProperty("model_id") String modelId,
    @JsonProperty("chat") CapabilityState chat,
    @JsonProperty("streaming") CapabilityState streaming,
    @JsonProperty("tools") CapabilityState tools,
    @JsonProperty("observed_tools") List<String> observedTools
) {
    public ModelCapability {
        optionFields=optionFields==null?null:List.copyOf(optionFields);
        observedTools=observedTools==null?null:List.copyOf(observedTools);
    }

}
