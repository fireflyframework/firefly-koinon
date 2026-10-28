// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

/** Authenticated file response, including conditional-download metadata. */
public record BinaryResponse(
    byte[] content, String contentType, String etag, String filename, boolean notModified) {
  public BinaryResponse {
    content = content.clone();
  }

  @Override
  public byte[] content() {
    return content.clone();
  }
}
