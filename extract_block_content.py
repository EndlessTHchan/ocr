"""Extract block_content fields from API JSON results.

Also produce a screen-reader-friendly text output.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


KEEP_LABELS = {
    "doc_title",
    "paragraph_title",
    "content_title",
    "abstract_title",
    "reference_title",
    "table_title",
    "text",
    "ocr",
    "table",
    "formula",
    "display_formula",
    "reference_content",
}

TITLE_LABELS = {
    "doc_title",
    "paragraph_title",
    "content_title",
    "abstract_title",
    "reference_title",
    "table_title",
}

TABLE_LABELS = {"table"}


def _normalize_text(text: str) -> str:
    s = text.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_block_content(data: dict) -> list[str]:
    blocks: list[str] = []
    for page in data.get("layoutParsingResults", []):
        pruned = page.get("prunedResult", {})
        for item in pruned.get("parsing_res_list", []):
            text = item.get("block_content")
            if text:
                blocks.append(str(text))
    return blocks


def extract_spoken_blocks(data: dict) -> list[str]:
    spoken: list[str] = []
    for page in data.get("layoutParsingResults", []):
        pruned = page.get("prunedResult", {})
        items = pruned.get("parsing_res_list", [])

        def _order_key(item: dict) -> tuple[int, int]:
            order = item.get("block_order")
            block_id = item.get("block_id")
            order_val = int(order) if isinstance(order, int) else 1_000_000
            id_val = int(block_id) if isinstance(block_id, int) else 1_000_000
            return (order_val, id_val)

        for item in sorted(items, key=_order_key):
            label = str(item.get("block_label") or "")
            if label and label not in KEEP_LABELS:
                continue
            text = _normalize_text(str(item.get("block_content") or ""))
            if not text:
                continue
            if label in TITLE_LABELS:
                spoken.append(f"\n标题：{text}\n")
            elif label in TABLE_LABELS:
                spoken.append(f"\n表格：\n{text}\n")
            else:
                spoken.append(text)
    return [t for t in spoken if t.strip()]


def main() -> None:
    in_path = Path("output/result.json")
    out_txt = Path("output/block_content.txt")
    out_json = Path("output/block_content.json")
    out_spoken_txt = Path("output/spoken_output.txt")
    out_spoken_json = Path("output/spoken_output.json")

    if not in_path.exists():
        raise SystemExit(f"Missing input: {in_path}")

    data = json.loads(in_path.read_text(encoding="utf-8"))
    blocks = extract_block_content(data)
    spoken = extract_spoken_blocks(data)

    out_txt.parent.mkdir(parents=True, exist_ok=True)
    out_txt.write_text("\n\n".join(blocks), encoding="utf-8")
    out_json.write_text(json.dumps(blocks, ensure_ascii=False, indent=2), encoding="utf-8")
    out_spoken_txt.write_text("\n\n".join(spoken), encoding="utf-8")
    out_spoken_json.write_text(json.dumps(spoken, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"Saved {len(blocks)} blocks to {out_txt} and {out_json}; "
        f"spoken output to {out_spoken_txt} and {out_spoken_json}"
    )


if __name__ == "__main__":
    main()
