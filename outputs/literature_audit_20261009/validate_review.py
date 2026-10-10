import argparse
import hashlib
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("path", type=Path)
parser.add_argument("--renumber", action="store_true")
args = parser.parse_args()
text = args.path.read_text(encoding="utf-8")
body, refs = text.split("## 参考文献", 1)
records = {int(m.group(1)): m.group(2).strip() for m in re.finditer(r"^\[(\d+)\]\s+(.+)$", refs, re.M)}
pattern = re.compile(r"\[(\d+(?:\s*[,，]\s*\d+)*)\]")
order = []
for match in pattern.finditer(body):
    for value in re.split(r"\s*[,，]\s*", match.group(1)):
        number = int(value)
        if number not in order:
            order.append(number)
missing = sorted(set(order) - set(records))
if missing:
    raise SystemExit(f"Undefined citations: {missing}")
mapping = {old: i + 1 for i, old in enumerate(order)}
if args.renumber:
    # Mechanical, simultaneous citation renumbering; prose is never generated here.
    body = pattern.sub(lambda m: "[" + ",".join(str(mapping[int(x)]) for x in re.split(r"\s*[,，]\s*", m.group(1))) + "]", body)
    refs = "\n\n" + "\n\n".join(f"[{mapping[old]}] {records[old]}" for old in order) + "\n"
    text = body + "## 参考文献" + refs
    args.path.write_text(text, encoding="utf-8")

han = lambda value: len(re.findall(r"[\u4e00-\u9fff]", value))
chapters = re.split(r"(?=^## [一二三四]、)", body, flags=re.M)
stats = {
    "file": str(args.path),
    "sha256": hashlib.sha256(text.encode()).hexdigest(),
    "body_han_including_title_abstract_keywords_headings_table": han(body),
    "body_han_excluding_front_matter": han(body[body.find("## 一、"):]),
    "all_han_including_references": han(text),
    "chapter_han": [{"label": c.splitlines()[0], "han": han(c)} for c in chapters if c.strip()],
    "citation_first_occurrence_old": order,
    "citation_mapping_old_to_new": mapping,
    "unused_old_references": sorted(set(records) - set(order)),
    "reference_count_final": len(order),
    "body_in_4800_5200": 4800 <= han(body) <= 5200,
    "prose_only_han_excluding_tables_and_headings": han("\n".join(line for line in body.splitlines() if not line.startswith(("|", "#")))),
}
print(json.dumps(stats, ensure_ascii=False, indent=2))
