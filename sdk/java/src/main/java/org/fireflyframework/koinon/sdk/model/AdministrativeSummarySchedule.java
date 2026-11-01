// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical AdministrativeSummarySchedule contract. */
public record AdministrativeSummarySchedule(
    @JsonProperty("cadence") AdministrativeSummaryScheduleCadence cadence,
    @JsonProperty("schedule") DigestSchedule schedule
) {

    public static AdministrativeSummarySchedule empty(){return new AdministrativeSummarySchedule(null,null);}
    public AdministrativeSummarySchedule withCadence(AdministrativeSummaryScheduleCadence value){return new AdministrativeSummarySchedule(value,schedule);}
    public AdministrativeSummarySchedule withSchedule(DigestSchedule value){return new AdministrativeSummarySchedule(cadence,value);}
}
