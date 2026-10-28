# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from flycanon.core.services.ingestion.chunker import ParagraphChunker
from flycanon.core.services.ingestion.loaders import LoadedDocument, Section


def test_offsets_count_unicode_code_points_in_the_emitted_chunk_stream():
    document = LoadedDocument(sections=[Section(body="  A😀BCDEFGHIJKLMN  ", path=["Heading"], page=2)])
    chunks = ParagraphChunker(chunk_size_tokens=2, overlap_tokens=1, tokens_per_char=0.25).chunk(document)
    assert len(chunks) > 1
    assert chunks[0].content == "A😀BCDEFG"
    assert chunks[0].char_start == 0 and chunks[0].char_end == 8
    assert len(chunks[0].content.encode("utf-16-le")) // 2 == 9
    assert chunks[1].char_start == chunks[0].char_end + 1
    assert chunks[1].content.startswith(chunks[0].content[-4:])
    assert all(chunk.section_path == "Heading" and chunk.page == 2 for chunk in chunks)
