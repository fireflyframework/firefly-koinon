# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class BrowserSessionView(BaseModel):
    subject: str
    authenticated: bool
    authentication_method: Literal["bearer", "oidc-session"]
    expires_at: datetime | None
    authenticated_at: datetime | None
    server_time: datetime
