// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record TableProvenanceFilter(String snapshotId) {
public static TableProvenanceFilter empty(){return new TableProvenanceFilter(null);}
public TableProvenanceFilter withSnapshotId(String value){return new TableProvenanceFilter(value);}
public RequestOptions applyTo(RequestOptions options){
Objects.requireNonNull(snapshotId,"snapshot_id is required");
if(snapshotId!=null)options=options.query("snapshot_id",String.valueOf(snapshotId));
return options;}
}
