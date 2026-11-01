// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical DigestSchedulePreview contract. */
public record DigestSchedulePreview(
    @JsonProperty("digest") CommunicationPolicyAllowedDigests digest,
    @JsonProperty("schedule") DigestSchedule schedule,
    @JsonProperty("time_zone") String timeZone,
    @JsonProperty("next_run_at") Instant nextRunAt,
    @JsonProperty("next_run_local") String nextRunLocal,
    @JsonProperty("window_start") Instant windowStart,
    @JsonProperty("window_end") Instant windowEnd,
    @JsonProperty("dst_policy") DigestSchedulePreviewDstPolicy dstPolicy,
    @JsonProperty("effective_locale") String effectiveLocale,
    @JsonProperty("locale_origin") CommunicationCapabilitiesLocaleOrigin localeOrigin
) {

}
