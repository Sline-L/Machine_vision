from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
ET.register_namespace("w", W)


def q(name: str) -> str:
    return f"{{{W}}}{name}"


def ensure(parent: ET.Element, tag: str) -> ET.Element:
    item = parent.find(f"w:{tag}", NS)
    if item is None:
        item = ET.SubElement(parent, q(tag))
    return item


def set_style(styles: ET.Element, style_id: str, *, size: int, bold: bool = False,
              before: int = 0, after: int = 120, keep: bool = False) -> None:
    style = styles.find(f"w:style[@w:styleId='{style_id}']", NS)
    if style is None:
        return
    ppr = ensure(style, "pPr")
    spacing = ensure(ppr, "spacing")
    spacing.set(q("before"), str(before))
    spacing.set(q("after"), str(after))
    spacing.set(q("line"), "300")
    spacing.set(q("lineRule"), "auto")
    if keep:
        ensure(ppr, "keepNext")
        ensure(ppr, "keepLines")
    rpr = ensure(style, "rPr")
    fonts = ensure(rpr, "rFonts")
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(q(key), "Noto Sans CJK SC")
    color = ensure(rpr, "color")
    color.set(q("val"), "000000")
    sz = ensure(rpr, "sz")
    sz.set(q("val"), str(size))
    szcs = ensure(rpr, "szCs")
    szcs.set(q("val"), str(size))
    if bold:
        ensure(rpr, "b")
        ensure(rpr, "bCs")


def make_page_break() -> ET.Element:
    p = ET.Element(q("p"))
    r = ET.SubElement(p, q("r"))
    br = ET.SubElement(r, q("br"))
    br.set(q("type"), "page")
    return p


def patch_styles(data: bytes) -> bytes:
    root = ET.fromstring(data)
    defaults = root.find("w:docDefaults/w:rPrDefault/w:rPr", NS)
    if defaults is not None:
        fonts = ensure(defaults, "rFonts")
        for key in ("ascii", "hAnsi", "eastAsia", "cs"):
            fonts.set(q(key), "Noto Sans CJK SC")
        ensure(defaults, "color").set(q("val"), "000000")
    set_style(root, "Normal", size=21, after=120)
    set_style(root, "BodyText", size=21, after=120)
    set_style(root, "Title", size=42, bold=True, before=720, after=260, keep=True)
    set_style(root, "Subtitle", size=24, before=80, after=300, keep=True)
    set_style(root, "Heading1", size=30, bold=True, before=100, after=180, keep=True)
    set_style(root, "Heading2", size=30, bold=True, before=100, after=180, keep=True)
    set_style(root, "Heading3", size=25, bold=True, before=240, after=120, keep=True)
    set_style(root, "Heading4", size=22, bold=True, before=180, after=100, keep=True)
    set_style(root, "Caption", size=18, after=180, keep=True)
    set_style(root, "Table", size=17, after=90)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def patch_document(data: bytes) -> bytes:
    root = ET.fromstring(data)
    body = root.find("w:body", NS)
    if body is None:
        return data
    children = list(body)
    for child in children:
        if child.tag != q("p"):
            continue
        style = child.find("w:pPr/w:pStyle", NS)
        if style is not None and style.get(q("val")) == "Heading2":
            index = list(body).index(child)
            body.insert(index, make_page_break())
    sect = body.find("w:sectPr", NS)
    if sect is not None:
        size = ensure(sect, "pgSz")
        size.set(q("w"), "12240")
        size.set(q("h"), "15840")
        margins = ensure(sect, "pgMar")
        margins.set(q("top"), "900")
        margins.set(q("right"), "900")
        margins.set(q("bottom"), "900")
        margins.set(q("left"), "900")
        margins.set(q("header"), "432")
        margins.set(q("footer"), "432")
        margins.set(q("gutter"), "0")
    for table in body.findall(".//w:tbl", NS):
        props = ensure(table, "tblPr")
        borders = ensure(props, "tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            edge = ensure(borders, side)
            edge.set(q("val"), "single")
            edge.set(q("sz"), "4")
            edge.set(q("space"), "0")
            edge.set(q("color"), "D9D9D9")
        rows = table.findall("w:tr", NS)
        for row in rows:
            ensure(ensure(row, "trPr"), "cantSplit")
        if rows:
            trpr = ensure(rows[0], "trPr")
            ensure(trpr, "tblHeader")
            for cell in rows[0].findall("w:tc", NS):
                tcpr = ensure(cell, "tcPr")
                shd = ensure(tcpr, "shd")
                shd.set(q("fill"), "D9EAF7")
                valign = ensure(tcpr, "vAlign")
                valign.set(q("val"), "center")
                for run in cell.findall(".//w:r", NS):
                    rpr = ensure(run, "rPr")
                    ensure(rpr, "b")
                    ensure(rpr, "bCs")
                    ensure(rpr, "color").set(q("val"), "000000")
        for row_index, row in enumerate(rows[1:], start=1):
            for cell in row.findall("w:tc", NS):
                tcpr = ensure(cell, "tcPr")
                ensure(tcpr, "vAlign").set(q("val"), "center")
                margins = ensure(tcpr, "tcMar")
                for side in ("top", "bottom", "left", "right"):
                    node = ensure(margins, side)
                    node.set(q("w"), "60")
                    node.set(q("type"), "dxa")
                if row_index % 2 == 0:
                    ensure(tcpr, "shd").set(q("fill"), "F5F8FA")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def main() -> None:
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    with zipfile.ZipFile(source) as zin:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            temp_path = Path(tmp.name)
        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/styles.xml":
                    data = patch_styles(data)
                elif item.filename == "word/document.xml":
                    data = patch_document(data)
                zout.writestr(item, data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(temp_path, destination)
    temp_path.unlink()


if __name__ == "__main__":
    main()
