// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical SystemInformation contract. */
public record SystemInformation(
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("checked_at") Instant checkedAt,
    @JsonProperty("product") SystemInformationProduct product,
    @JsonProperty("components") List<SystemComponentVersion> components,
    @JsonProperty("serving_role") SystemInformationServingRole servingRole,
    @JsonProperty("capabilities") SystemCapabilities capabilities,
    @JsonProperty("limits") List<SystemLimit> limits,
    @JsonProperty("build_revision") String buildRevision,
    @JsonProperty("license_expression") SystemInformationLicenseExpression licenseExpression,
    @JsonProperty("copyright") SystemInformationCopyright copyright,
    @JsonProperty("artifacts") List<SystemArtifact> artifacts
) {
    public SystemInformation {
        components=components==null?null:List.copyOf(components);
        limits=limits==null?null:List.copyOf(limits);
        artifacts=artifacts==null?null:List.copyOf(artifacts);
    }

}
