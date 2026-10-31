// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaIntake {
    public static UploadResponse upload(KoinonClient client, String tenant,
            String workspace, Path file, String mediaType, UploadMode mode) throws IOException {
        if (!Files.isRegularFile(file) || Files.size(file) == 0
                || Files.size(file) > 32L * 1024 * 1024) {
            throw new IllegalArgumentException("Choose a nonempty regular file up to 32 MiB");
        }
        var project = client.catalog(tenant).create(CatalogCreate.empty()
            .withKind("project").withName("Operations").withParentId(workspace));
        var collection = client.catalog(tenant).create(CatalogCreate.empty()
            .withKind("collection").withName("Policies").withParentId(project.id()));
        client.catalog(tenant).update(collection.id(), CatalogUpdate.empty()
            .withName("Approved policies"));
        return client.sources(tenant).upload(new SourceUpload(file, mediaType,
            workspace, project.id(), collection.id(), mode));
    }

    public static CatalogEntry archive(KoinonClient client, String tenant, String reviewedId) {
        return client.catalog(tenant).archive(reviewedId);
    }

    public static CatalogEntry restore(KoinonClient client, String tenant, String reviewedId) {
        return client.catalog(tenant).restore(reviewedId);
    }

    public static void deleteEmptyResource(KoinonClient client, String tenant, String reviewedId) {
        client.catalog(tenant).delete(reviewedId);
    }
}
