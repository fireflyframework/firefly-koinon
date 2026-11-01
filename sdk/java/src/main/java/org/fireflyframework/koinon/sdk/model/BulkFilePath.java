// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.net.http.HttpRequest;
import java.nio.file.Files;
import java.nio.file.FileSystems;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Objects;

/** A caller-owned original matching an already admitted manifest. */
public record BulkFilePath(Path file, long sizeBytes, String sha256) {
  public BulkFilePath {
    Objects.requireNonNull(file);
    Objects.requireNonNull(sha256);
    if (sizeBytes < 1 || sizeBytes > 134217728 || !sha256.matches("[a-f0-9]{64}"))
      throw new IllegalArgumentException("Supply the original's bounded size and SHA-256 manifest");
  }

  public Snapshot snapshot() {
    Path directory = null;
    try {
      var before = Files.readAttributes(file, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
      if (!before.isRegularFile() || before.size() != sizeBytes)
        throw new IllegalArgumentException("Original size differs from its admitted manifest");
      boolean posix = FileSystems.getDefault().supportedFileAttributeViews().contains("posix");
      directory = posix
          ? Files.createTempDirectory("koinon-original-", PosixFilePermissions.asFileAttribute(
              PosixFilePermissions.fromString("rwx------")))
          : Files.createTempDirectory("koinon-original-");
      var target = directory.resolve("original");
      if (posix) Files.createFile(target, PosixFilePermissions.asFileAttribute(
          PosixFilePermissions.fromString("rw-------")));
      else Files.createFile(target);
      var digest = MessageDigest.getInstance("SHA-256");
      long count = 0;
      try (var source = Files.newInputStream(file, LinkOption.NOFOLLOW_LINKS);
           var output = Files.newOutputStream(target)) {
        byte[] block = new byte[65536];
        int read;
        while ((read = source.read(block)) != -1) {
          count += read;
          if (count > sizeBytes) throw new IllegalArgumentException("Original grew during verification");
          digest.update(block, 0, read);
          output.write(block, 0, read);
        }
      }
      var after = Files.readAttributes(file, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
      if (count != sizeBytes || !HexFormat.of().formatHex(digest.digest()).equals(sha256)
          || !Objects.equals(before.fileKey(), after.fileKey())
          || !before.lastModifiedTime().equals(after.lastModifiedTime()))
        throw new IllegalArgumentException("Original differs from its admitted manifest");
      return new Snapshot(directory, target);
    } catch (IOException error) {
      cleanup(directory);
      throw new UncheckedIOException("Cannot prepare the selected original", error);
    } catch (NoSuchAlgorithmException error) {
      cleanup(directory);
      throw new IllegalStateException("SHA-256 is unavailable", error);
    } catch (RuntimeException error) {
      cleanup(directory);
      throw error;
    }
  }

  private static void cleanup(Path directory) {
    if (directory == null) return;
    var file = directory.resolve("original");
    try {
      Files.deleteIfExists(file);
      Files.deleteIfExists(directory);
    } catch (IOException error) {
      directory.toFile().deleteOnExit();
      file.toFile().deleteOnExit();
    }
  }

  /** Owned verified temporary bytes; the source path is never reopened by the HTTP publisher. */
  public static final class Snapshot implements AutoCloseable {
    private final Path directory;
    private final Path file;
    private InputStream source;
    private boolean supplied;
    private boolean closed;
    private Snapshot(Path directory, Path file) {
      this.directory = directory;
      this.file = file;
    }
    public synchronized HttpRequest.BodyPublisher publisher() throws IOException {
      if (closed || source != null) throw new IOException("Original publisher is already consumed");
      source = Files.newInputStream(file, LinkOption.NOFOLLOW_LINKS);
      var publisher = HttpRequest.BodyPublishers.ofInputStream(() -> {
        synchronized (this) {
          if (closed || supplied) return null;
          supplied = true;
          return source;
        }
      });
      return HttpRequest.BodyPublishers.fromPublisher(publisher, Files.size(file));
    }
    @Override public synchronized void close() {
      if (closed) return;
      closed = true;
      try {
        if (source != null) source.close();
      } catch (IOException ignored) {
        // The private snapshot still needs deletion if a transport closed its input first.
      } finally {
        cleanup(directory);
      }
    }
  }
}
