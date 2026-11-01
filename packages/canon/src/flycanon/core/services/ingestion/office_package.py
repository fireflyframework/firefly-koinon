# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Stream OOXML text from declared parts in document order; never decode media."""

import posixpath
import re
import zipfile
from urllib.parse import unquote, urlsplit
from xml.parsers import expat

import lxml.etree as etree


def _local(element):
    return etree.QName(element).localname


def _root(archive, name):
    with archive.open(name) as source:
        return etree.parse(
            source, etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
        ).getroot()


def _target(source, value):
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("Office relationship must name an internal package part")
    decoded = unquote(parsed.path, errors="strict")
    target = posixpath.normpath(
        decoded.lstrip("/") if decoded.startswith("/") else posixpath.join(posixpath.dirname(source), decoded)
    )
    if target.startswith("../") or target in {"..", "."} or "\\" in target:
        raise ValueError("Office relationship escapes its package")
    return target


def _relationships(archive, names, source):
    path = (
        posixpath.join(posixpath.dirname(source), "_rels", posixpath.basename(source) + ".rels")
        if source
        else "_rels/.rels"
    )
    if path not in names:
        return {}
    result = {}
    for item in _root(archive, path):
        if _local(item) != "Relationship":
            continue
        identifier = item.get("Id")
        if not identifier or identifier in result:
            raise ValueError("Office relationships require unique identities")
        if item.get("TargetMode") == "External":
            continue
        target = _target(source, item.get("Target", ""))
        if target not in names:
            raise ValueError("Office relationship part is missing")
        result[identifier] = (item.get("Type", "").rsplit("/", 1)[-1], target)
    return result


def _preflight(archive, policy):
    names = set()
    expanded = 0
    members = archive.infolist()
    if len(members) > policy.archive_members_max:
        raise ValueError("Office package has too many members")
    for member in members:
        name = member.filename
        if (
            name in names
            or name.startswith("/")
            or "\\" in name
            or ".." in name.split("/")
            or member.flag_bits & 1
        ):
            raise ValueError("Office package contains an unsafe or duplicate member")
        names.add(name)
        count = 0
        parser = None
        if name.endswith((".xml", ".rels")):
            parser = expat.ParserCreate()

            def deny(*args):
                raise ValueError("Office XML declarations and entities are unsupported")

            parser.StartDoctypeDeclHandler = deny
            parser.EntityDeclHandler = deny
            parser.ExternalEntityRefHandler = deny
        with archive.open(member) as stream:
            while data := stream.read(65536):
                count += len(data)
                expanded += len(data)
                if expanded > policy.expanded_max_bytes or (
                    parser is not None and count > policy.xml_max_bytes
                ):
                    raise ValueError("Office package expansion exceeds its resource policy")
                if parser is not None:
                    parser.Parse(data, False)
        if parser is not None:
            parser.Parse(b"", True)
        if count != member.file_size:
            raise ValueError("Office member size differs from its header")
    return names


def _main(archive, names, kind):
    relationships = _relationships(archive, names, "")
    main = [target for relation, target in relationships.values() if relation == "officeDocument"]
    if len(main) == 1:
        return main[0]
    if len(main) > 1:
        raise ValueError("Office package declares multiple main documents")
    if "[Content_Types].xml" in names:
        marker = "wordprocessingml.document.main" if kind == "docx" else "presentationml.presentation.main"
        main = [
            _target("", item.get("PartName", ""))
            for item in _root(archive, "[Content_Types].xml")
            if marker in item.get("ContentType", "")
        ]
        if len(main) == 1 and main[0] in names:
            return main[0]
    # Compatibility with existing minimal producer fixtures. Actual packages declare their main part.
    standard = "word/document.xml" if kind == "docx" else "ppt/presentation.xml"
    if standard in names:
        return standard
    if kind == "pptx":
        # Older minimal fixtures contain only slide parts; their numeric names define their order.
        slides = [name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)]
        if slides:
            return None
    raise ValueError("Office package has no supported main document")


def _paragraph_text(element):
    parts = []
    for child in element.iter():
        name = _local(child)
        if name == "t" and child.text:
            parts.append(child.text)
        elif name == "tab":
            parts.append("\t")
        elif name in {"br", "cr"}:
            parts.append("\n")
    return "".join(parts).strip()


def extract_office(path, kind, policy):
    sections = []
    size = 0

    def append(body, heading, page=None):
        nonlocal size
        if not body:
            return
        size += len(body.encode()) + sum(len(part.encode()) for part in heading) + 16
        if size > policy.text_max_bytes or len(sections) >= policy.chunks_max:
            raise ValueError("Office text or sections exceed their resource policy")
        sections.append({"body": body, "path": list(heading), "page": page, "order": len(sections)})

    with zipfile.ZipFile(path) as archive:
        names = _preflight(archive, policy)
        main = _main(archive, names, kind)
        relations = _relationships(archive, names, main) if main is not None else {}
        if kind == "pptx":
            if main is None:
                parts = sorted(
                    (name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
                    key=lambda name: int(name.removeprefix("ppt/slides/slide").removesuffix(".xml")),
                )
            else:
                parts = []
                for element in _root(archive, main).iter():
                    if _local(element) != "sldId":
                        continue
                    ids = [
                        value
                        for key, value in element.attrib.items()
                        if key.startswith("{") and key.rsplit("}", 1)[-1] == "id"
                    ]
                    if len(ids) != 1 or ids[0] not in relations or relations[ids[0]][0] != "slide":
                        raise ValueError("Slide order has an unresolved relationship")
                    parts.append(relations[ids[0]][1])
                if not parts:
                    raise ValueError("Presentation has no declared slides")
            selected = [(name, [f"Slide {index + 1}"], index + 1) for index, name in enumerate(parts)]
        else:
            selected = [
                (target, ["Header"], None) for relation, target in relations.values() if relation == "header"
            ]
            selected.append((main, [], None))
            selected.extend(
                (target, ["Footer"], None) for relation, target in relations.values() if relation == "footer"
            )
        for name, heading, page in selected:
            slide_text = []
            headings = list(heading)
            with archive.open(name) as stream:
                for _, element in etree.iterparse(
                    stream,
                    events=("end",),
                    resolve_entities=False,
                    no_network=True,
                    load_dtd=False,
                    huge_tree=False,
                ):
                    if _local(element) != "p":
                        continue
                    text = _paragraph_text(element)
                    if kind == "pptx":
                        slide_text.append(text)
                        if sum(len(item.encode()) for item in slide_text) > policy.text_max_bytes:
                            raise ValueError("Slide text exceeds its resource policy")
                    else:
                        style = next(
                            (
                                child.get("{" + etree.QName(child).namespace + "}val")
                                if etree.QName(child).namespace
                                else child.get("val")
                                for child in element.iter()
                                if _local(child) == "pStyle"
                            ),
                            None,
                        )
                        match = re.fullmatch(r"Heading\s*(\d+)", style or "", re.IGNORECASE)
                        if match and text and not heading:
                            level = min(9, int(match.group(1)))
                            headings = headings[: level - 1] + [text]
                        else:
                            append(text, headings, page)
                    element.clear()
                    while element.getprevious() is not None:
                        del element.getparent()[0]
            if kind == "pptx":
                append("\n".join(line for line in slide_text if line), heading, page)
        properties = {}
        if "docProps/core.xml" in names:
            fields = {
                "title",
                "creator",
                "subject",
                "description",
                "created",
                "modified",
                "keywords",
                "lastModifiedBy",
            }
            for element in _root(archive, "docProps/core.xml").iter():
                if _local(element) in fields and element.text:
                    if len(element.text.encode()) > 4096:
                        raise ValueError("Office metadata exceeds its resource policy")
                    properties[_local(element)] = element.text
    text = "\n\n".join(
        (
            "\n".join("#" * min(index + 2, 6) + " " + label for index, label in enumerate(section["path"]))
            + "\n"
            + section["body"]
        ).strip()
        for section in sections
    )
    if len(text.encode()) > policy.text_max_bytes:
        raise ValueError("Office emitted text exceeds its resource policy")
    return (
        text,
        sections,
        {
            "parser": "bounded-ooxml",
            "extraction_coverage": "text_and_tables",
            "image_interpretation": "not_performed",
            "original_media": "retained",
            "properties": properties,
            "page_basis": "slide_order" if kind == "pptx" else "not_available",
        },
    )
