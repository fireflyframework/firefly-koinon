// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

import java.util.Objects;

public record AvatarUpload(byte[] content, ImageMediaType mediaType) {
  public AvatarUpload {
    Objects.requireNonNull(content);
    Objects.requireNonNull(mediaType);
    if (content.length > 2097152) throw new IllegalArgumentException("Avatar exceeds2MiB");
    content = content.clone();
  }

  @Override
  public byte[] content() {
    return content.clone();
  }
}
