// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical DeploymentConfiguration contract. */
public record DeploymentConfiguration(
    @JsonProperty("ownership") DeploymentConfigurationOwnership ownership,
    @JsonProperty("read_only") Boolean readOnly,
    @JsonProperty("datasources") List<DeploymentDatasource> datasources,
    @JsonProperty("storage") List<DeploymentStorage> storage,
    @JsonProperty("indexes") List<DeploymentIndex> indexes,
    @JsonProperty("metrics") MetricsObservation metrics,
    @JsonProperty("limits") OperationalLimits limits
) {
    public DeploymentConfiguration {
        datasources=datasources==null?null:List.copyOf(datasources);
        storage=storage==null?null:List.copyOf(storage);
        indexes=indexes==null?null:List.copyOf(indexes);
    }

}
