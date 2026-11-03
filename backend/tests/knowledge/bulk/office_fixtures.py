# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Small genuine Office packages, generated rather than retained as binary fixtures."""

from io import BytesIO


def office_original(kind: str) -> bytes:
    output = BytesIO()
    if kind == "docx":
        from docx import Document

        document = Document()
        document.add_heading("Quarterly review", level=1)
        document.add_paragraph("North region revenue is 125.")
        table = document.add_table(rows=2, cols=2)
        for row, values in zip(table.rows, (("Region", "Revenue"), ("North", "125")), strict=True):
            for cell, value in zip(row.cells, values, strict=True):
                cell.text = value
        document.sections[0].header.paragraphs[0].text = "Review header"
        document.save(output)
    elif kind == "pptx":
        from pptx import Presentation

        presentation = Presentation()
        for title, body in (("Quarterly review", "North region revenue is 125."), ("Next quarter", "South")):
            slide = presentation.slides.add_slide(presentation.slide_layouts[1])
            slide.shapes.title.text = title
            slide.placeholders[1].text = body
        presentation.save(output)
    elif kind == "xlsx":
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Revenue"
        for row in (("Region", "Revenue"), ("North", 125), ("South", 250)):
            sheet.append(row)
        workbook.save(output)
        workbook.close()
    elif kind == "csv":
        return b"Region,Revenue\nNorth,125\nSouth,250\n"
    else:
        raise ValueError("Unknown fixture format")
    return output.getvalue()
