// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

import java.nio.file.Path;
import java.util.Objects;

public record SourceUpload(
    Path file,
    String mediaType,
    String workspaceId,
    String projectId,
    String parentId,
    UploadMode mode) {
  public SourceUpload {
    Objects.requireNonNull(file);
    Objects.requireNonNull(workspaceId);
    Objects.requireNonNull(projectId);
    Objects.requireNonNull(parentId);
    Objects.requireNonNull(mode);
  }
}
