# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from flyquery.web.conventions import FireflyHTTPException


class GlossaryTermExists(FireflyHTTPException):
    status = 409
    code = "GLOSSARY_TERM_EXISTS"
    title = "Glossary term already exists"

    def __init__(self):
        super().__init__("This workspace already contains that glossary term")


class GlossaryRevisionConflict(FireflyHTTPException):
    status = 409
    code = "GLOSSARY_REVISION_CONFLICT"
    title = "Glossary term changed"

    def __init__(self):
        super().__init__("Reload the current glossary term before changing it")


class GlossaryRevisionRequired(FireflyHTTPException):
    status = 428
    code = "GLOSSARY_REVISION_REQUIRED"
    title = "Glossary revision required"

    def __init__(self):
        super().__init__("Supply the current updated_at timestamp in If-Match")


class GlossaryPayloadInvalid(FireflyHTTPException):
    status = 422
    code = "INVALID_GLOSSARY_PAYLOAD"
    title = "Invalid glossary payload"
