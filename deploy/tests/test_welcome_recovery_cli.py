# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest

spec=importlib.util.spec_from_file_location("welcome_recovery_cli",Path(__file__).parents[1]/"communications.py")
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)


def arguments():
    return ["welcome-recovery","--delivery-id",str(uuid4()),"--contact-id",str(uuid4()),
        "--expected-generation","1","--expected-contact-revision","1","--operation-id",str(uuid4()),
        "--reason","recipient_reported_not_received","--acknowledge-possible-duplicate"]


def test_manual_recovery_cli_requires_duplicate_acknowledgment_and_no_fabricated_identity():
    value=cli.arguments(arguments())
    assert value.acknowledge_possible_duplicate and value.expected_generation==1
    with pytest.raises(SystemExit):cli.arguments(arguments()[:-1])
    for extra in (["--email","other@example.test"],["--owner","made-up"],["--role","admin"]):
        with pytest.raises(SystemExit):cli.arguments([*arguments(),*extra])


def test_inspection_cli_is_an_existing_delivery_operation_not_a_send_payload():
    value=cli.arguments(["inspect-delivery","--delivery-id",str(uuid4()),"--expected-generation","1", "--operation-id",str(uuid4())])
    assert value.command=="inspect-delivery"
    with pytest.raises(SystemExit):cli.arguments(["inspect-delivery","--delivery-id",str(uuid4()),"--body","x"])
