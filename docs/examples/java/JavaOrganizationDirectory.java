// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaOrganizationDirectory {
    public static OrganizationPersonPage browse(KoinonClient client, String tenant,
            String authorizedWorkspace, String query, int page) {
        return client.organizationPeople(tenant).list(OrganizationPeopleFilter.empty()
            .withWorkspaceId(authorizedWorkspace).withQ(query).withPage(page).withPageSize(25));
    }

    public static OrganizationPerson changeLocalTitle(KoinonClient client, String tenant,
            OrganizationPerson reviewed, String title) {
        if (reviewed.id() == null) throw new IllegalArgumentException("Create an assignment first");
        return client.organizationPeople(tenant).update(reviewed.id(), OrganizationPersonPatch.empty()
            .withExpectedRevision(reviewed.revision()).withJobTitle(title));
    }
}
