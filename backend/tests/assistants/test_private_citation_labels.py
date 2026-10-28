# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

from koinon.assistants.private_citations import PrivateCitationLabels


def test_known_citation_labels_are_filenames_across_every_stream_boundary():
    item = SimpleNamespace(id="90071992-5474-4099-9254-740992547409", filename="Renewal notes.md")
    value = f"According to Attachment {item.id}: {item.filename}, renewal is 47."
    expected = "According to Renewal notes.md, renewal is 47."
    for offset in range(len(value) + 1):
        labels = PrivateCitationLabels((item,))
        assert labels.feed(value[:offset]) + labels.feed(value[offset:]) + labels.finish() == expected
    labels = PrivateCitationLabels((item,))
    assert "".join(labels.feed(char) for char in value) + labels.finish() == expected


def test_unknown_labels_and_business_identifiers_are_not_rewritten():
    item = SimpleNamespace(id="bd7f2677-c56c-467b-b1ef-c26e85af0589", filename="Facts.md")
    value = (
        f"The invoice reference is {item.id}. "
        f"Attachment {item.id}: Another file.md; "
        "Attachment 041ad7a2-b623-451f-914c-b0bca2572705: Facts.md."
    )
    labels = PrivateCitationLabels((item,))
    assert "".join(labels.feed(char) for char in value) + labels.finish() == value


def test_incomplete_citation_and_no_selected_files_are_preserved():
    item = SimpleNamespace(id="file", filename="Notes.md")
    labels = PrivateCitationLabels((item,))
    assert labels.feed("Value: Attachment fi") + labels.finish() == "Value: Attachment fi"
    labels = PrivateCitationLabels(())
    assert labels.feed("Attachment file: Notes.md") + labels.finish() == "Attachment file: Notes.md"


def test_canonical_context_header_uses_filename_while_legitimate_file_uuid_remains_exact():
    from koinon.assistants.attachment_input import private_file_text

    item = SimpleNamespace(id="bd7f2677-c56c-467b-b1ef-c26e85af0589", filename="Facts.md")
    body = f"Invoice ID: {item.id}\nA separate Attachment unknown: file.md"
    assert (
        private_file_text(item, f"Attachment {item.id}: {item.filename}\n" + body)
        == "File: Facts.md\n" + body
    )
    assert private_file_text(item, body) == body
