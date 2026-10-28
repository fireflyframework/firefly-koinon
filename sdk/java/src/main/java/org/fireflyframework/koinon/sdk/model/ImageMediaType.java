// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

public enum ImageMediaType {
  PNG("image/png"),
  JPEG("image/jpeg"),
  WEBP("image/webp");
  private final String value;

  ImageMediaType(String value) {
    this.value = value;
  }

  public String value() {
    return value;
  }
}
