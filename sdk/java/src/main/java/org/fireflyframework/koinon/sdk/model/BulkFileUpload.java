// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

import java.util.Objects;

public record BulkFileUpload(byte[] content) {
  public BulkFileUpload {
    Objects.requireNonNull(content);
    if (content.length < 1 || content.length > 134217728)
      throw new IllegalArgumentException("Choose a nonempty original of at most 128 MiB");
    content = content.clone();
  }
  @Override public byte[] content() { return content.clone(); }
}
