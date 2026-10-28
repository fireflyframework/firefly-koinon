// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical DeploymentDatasource contract. */
public record DeploymentDatasource(
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("available") Boolean available,
    @JsonProperty("status") ObservationStatus status,
    @JsonProperty("observed_at") Instant observedAt,
    @JsonProperty("reason") String reason,
    @JsonProperty("id") String id,
    @JsonProperty("kind") DeploymentDatasourceKind kind,
    @JsonProperty("driver") String driver,
    @JsonProperty("pool") ConnectionPool pool,
    @JsonProperty("pool_usage") PoolUsage poolUsage,
    @JsonProperty("role_policy") RoleObservation rolePolicy
) {

}
