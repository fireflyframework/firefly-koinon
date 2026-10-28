// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

import java.nio.file.Path;
import java.util.Objects;

public record TableReplacement(Path file, String mediaType) {
  public TableReplacement {
    Objects.requireNonNull(file);
  }
}
