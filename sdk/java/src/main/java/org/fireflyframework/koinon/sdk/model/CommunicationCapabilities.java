// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical CommunicationCapabilities contract. */
public record CommunicationCapabilities(
    @JsonProperty("state") CommunicationCapabilitiesState state,
    @JsonProperty("provider_label") String providerLabel,
    @JsonProperty("sender_name") String senderName,
    @JsonProperty("sender_address") String senderAddress,
    @JsonProperty("reply_to") String replyTo,
    @JsonProperty("sender_options") List<VerifiedSenderOption> senderOptions,
    @JsonProperty("public_address_configured") Boolean publicAddressConfigured,
    @JsonProperty("public_url") String publicUrl,
    @JsonProperty("acceptance_base") String acceptanceBase,
    @JsonProperty("issues") List<CommunicationIssue> issues,
    @JsonProperty("effective_locale") String effectiveLocale,
    @JsonProperty("locale_origin") CommunicationCapabilitiesLocaleOrigin localeOrigin
) {
    public CommunicationCapabilities {
        senderOptions=senderOptions==null?null:List.copyOf(senderOptions);
        issues=issues==null?null:List.copyOf(issues);
    }

}
