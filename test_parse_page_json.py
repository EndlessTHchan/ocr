"""Test parser for per-page JSON output.

Reads out/pages/XXXX.json, extracts AIStudio parsing_res_list when present,
and writes ordered text outputs for quick inspection.
"""

from __future__ import annotations

import argparse
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


def _order_key(item: dict) -> tuple[int, int]:
    order = item.get("block_order")
    block_id = item.get("block_id")
    order_val = int(order) if isinstance(order, int) else 1_000_000
    id_val = int(block_id) if isinstance(block_id, int) else 1_000_000
    return (order_val, id_val)


def _extract_items(page: dict) -> list[dict]:
    aistudio = page.get("aistudio_result")
    if isinstance(aistudio, dict):
        pages = aistudio.get("layoutParsingResults")
        if isinstance(pages, list) and pages:
            first = pages[0]
            pruned = first.get("prunedResult") if isinstance(first, dict) else None
            if isinstance(pruned, dict):
                items = pruned.get("parsing_res_list", [])
                if isinstance(items, list):
                    return items
            if isinstance(first, dict):
                items = first.get("parsing_res_list", [])
                if isinstance(items, list):
                    return items
    return []


def _extract_block_content(items: list[dict]) -> list[str]:
    out: list[str] = []
    for item in sorted(items, key=_order_key):
        text = item.get("block_content")
        if text:
            out.append(str(text))
    return out


def _extract_spoken(items: list[dict]) -> list[str]:
    spoken: list[str] = []
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
    parser = argparse.ArgumentParser(description="Test parse a per-page JSON file.")
    parser.add_argument(
        "--input",
        default="out/pages/0015.json",
        help="Path to per-page JSON (default: out/pages/0015.json)",
    )
    parser.add_argument(
        "--out-dir",
        default="output",
        help="Output directory for extracted text (default: output)",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        raise SystemExit(f"Missing input: {in_path}")

    page = json.loads(in_path.read_text(encoding="utf-8"))
    items = _extract_items(page)
    if not items:
        raise SystemExit("No aistudio_result parsing_res_list found in this page JSON")

    blocks = _extract_block_content(items)
    spoken = _extract_spoken(items)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "page_block_content.txt").write_text("\n\n".join(blocks), encoding="utf-8")
    (out_dir / "page_block_content.json").write_text(
        json.dumps(blocks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "page_spoken_output.txt").write_text("\n\n".join(spoken), encoding="utf-8")
    (out_dir / "page_spoken_output.json").write_text(
        json.dumps(spoken, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        "Saved page_block_content.txt/json and page_spoken_output.txt/json to "
        f"{out_dir} (blocks={len(blocks)}, spoken={len(spoken)})"
    )


if __name__ == "__main__":
    main()
