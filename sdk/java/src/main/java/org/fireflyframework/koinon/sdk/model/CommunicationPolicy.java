// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical CommunicationPolicy contract. */
public record CommunicationPolicy(
    @JsonProperty("revision") Long revision,
    @JsonProperty("sender_id") String senderId,
    @JsonProperty("rules") List<NotificationPreferenceRule> rules,
    @JsonProperty("digest_enabled") Boolean digestEnabled,
    @JsonProperty("can_update") Boolean canUpdate,
    @JsonProperty("allowed_digests") List<CommunicationPolicyAllowedDigests> allowedDigests,
    @JsonProperty("default_digest") CommunicationPolicyAllowedDigests defaultDigest,
    @JsonProperty("default_schedule") DigestSchedule defaultSchedule,
    @JsonProperty("admin_summaries") List<AdministrativeSummarySchedule> adminSummaries,
    @JsonProperty("default_locale") String defaultLocale
) {
    public CommunicationPolicy {
        rules=rules==null?null:List.copyOf(rules);
        allowedDigests=allowedDigests==null?null:List.copyOf(allowedDigests);
        adminSummaries=adminSummaries==null?null:List.copyOf(adminSummaries);
    }

}
