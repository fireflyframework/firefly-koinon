// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical NotificationPreferences contract. */
public record NotificationPreferences(
    @JsonProperty("admin_summaries_available") Boolean adminSummariesAvailable,
    @JsonProperty("admin_summaries_enabled") Boolean adminSummariesEnabled,
    @JsonProperty("revision") Long revision,
    @JsonProperty("rules") List<NotificationPreferenceRule> rules,
    @JsonProperty("digest") CommunicationPolicyAllowedDigests digest,
    @JsonProperty("allowed_digests") List<CommunicationPolicyAllowedDigests> allowedDigests,
    @JsonProperty("locale") String locale,
    @JsonProperty("time_zone") String timeZone,
    @JsonProperty("schedule") DigestSchedule schedule,
    @JsonProperty("next_run_at") Instant nextRunAt,
    @JsonProperty("next_run_local") String nextRunLocal,
    @JsonProperty("admin_summaries") Boolean adminSummaries,
    @JsonProperty("notification_locale") String notificationLocale,
    @JsonProperty("effective_locale") String effectiveLocale,
    @JsonProperty("locale_origin") CommunicationCapabilitiesLocaleOrigin localeOrigin
) {
    public NotificationPreferences {
        rules=rules==null?null:List.copyOf(rules);
        allowedDigests=allowedDigests==null?null:List.copyOf(allowedDigests);
    }

}
