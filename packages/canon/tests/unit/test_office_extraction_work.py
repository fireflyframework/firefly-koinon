# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bound text-accounting work independently of machine timing."""

import pytest
from flycanon.core.services.ingestion import office_package
from flycanon.core.services.ingestion.file_parser import DocumentFilePolicy
from pptx import Presentation
from pptx.util import Inches


def presentation(path, paragraphs):
    deck = Presentation()
    for values in paragraphs:
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        frame = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(5)).text_frame
        for index, value in enumerate(values):
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.text = value
    deck.save(path)
    return path


@pytest.mark.parametrize("paragraph_count", [32, 256])
def test_slide_budget_checks_process_linear_text_bytes(tmp_path, monkeypatch, paragraph_count):
    paragraphs = [
        f"Evidence {index}: " + ("conocimiento café " * 32).strip() for index in range(paragraph_count)
    ]
    slides = [paragraphs, ["Second slide retains its own provenance"]]
    path = presentation(tmp_path / "evidence.pptx", slides)
    encoded_bytes = 0
    original = office_package._paragraph_text

    class MeasuredText(str):
        def encode(self, encoding="utf-8", errors="strict"):
            nonlocal encoded_bytes
            result = super().encode(encoding, errors)
            encoded_bytes += len(result)
            return result

    monkeypatch.setattr(office_package, "_paragraph_text", lambda element: MeasuredText(original(element)))
    text, sections, metadata = office_package.extract_office(path, "pptx", DocumentFilePolicy())

    assert [section["body"] for section in sections] == ["\n".join(values) for values in slides]
    assert [section["page"] for section in sections] == [1, 2]
    assert paragraphs[-1] in text
    assert metadata["page_basis"] == "slide_order"
    input_text_bytes = sum(len(value.encode()) for values in slides for value in values)
    assert encoded_bytes <= 2 * input_text_bytes


def test_slide_budget_counts_unicode_bytes_before_publication(tmp_path):
    path = presentation(tmp_path / "unicode.pptx", [["🧠" * 300]])
    with pytest.raises(ValueError, match="Slide text exceeds"):
        office_package.extract_office(path, "pptx", DocumentFilePolicy(text_max_bytes=1000))
