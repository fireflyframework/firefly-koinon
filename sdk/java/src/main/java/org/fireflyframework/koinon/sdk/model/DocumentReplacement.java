// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

import java.nio.file.Path;
import java.util.Objects;

public record DocumentReplacement(
    Path file, String mediaType, Boolean acknowledgeChunkInvalidation) {
  public DocumentReplacement {
    Objects.requireNonNull(file);
  }
}
