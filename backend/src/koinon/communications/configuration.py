# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import bean, configuration

from koinon.catalog.ports import MembershipEventRecorder
from koinon.communications.events import CommunicationEvents
from koinon.communications.ports import AccountEventRecorder


@configuration
class CommunicationsConfiguration:
    @bean(name="communications.membership_events")
    def membership_events(self, events: CommunicationEvents) -> MembershipEventRecorder:
        return events

    @bean(name="communications.account_events")
    def account_events(self, events: CommunicationEvents) -> AccountEventRecorder:
        return events
