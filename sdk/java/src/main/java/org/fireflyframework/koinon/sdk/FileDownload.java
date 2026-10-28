// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk;

import java.nio.file.Path;

/** A completed streaming download. Existing files are never overwritten. */
public record FileDownload(
    Path path,
    long bytesWritten,
    String contentType,
    String etag,
    String filename,
    boolean notModified) {}
