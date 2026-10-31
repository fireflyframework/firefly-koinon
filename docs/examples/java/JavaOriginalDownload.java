// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import java.nio.file.Path;
import org.fireflyframework.koinon.sdk.FileDownload;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.RequestOptions;

public final class JavaOriginalDownload {
    public static FileDownload download(KoinonClient client, String tenant,
            String documentId, Path newTarget, String previousEtag) {
        var options = RequestOptions.defaults();
        if (previousEtag != null) options = options.header("If-None-Match", previousEtag);
        return client.documents(tenant).downloadOriginal(documentId, newTarget,
            256L * 1024 * 1024, options);
    }
}
