"""Parse PaddleOCR-VL/AIStudio JSON and export ordered text outputs."""

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


def _iter_pages(data: dict) -> list[dict]:
    pages = data.get("layoutParsingResults")
    if isinstance(pages, list) and pages:
        return pages
    pages = data.get("pages")
    if isinstance(pages, list) and pages:
        return pages
    return [data]


def _get_page_result(page: dict) -> dict:
    pruned = page.get("prunedResult")
    if isinstance(pruned, dict):
        return pruned
    return page


def _extract_page_meta(page: dict) -> dict:
    fields = {
        "input_path": page.get("input_path"),
        "page_index": page.get("page_index"),
        "model_settings": page.get("model_settings"),
        "use_doc_preprocessor": page.get("use_doc_preprocessor"),
        "use_layout_detection": page.get("use_layout_detection"),
        "use_chart_recognition": page.get("use_chart_recognition"),
        "format_block_content": page.get("format_block_content"),
        "doc_preprocessor_res": page.get("doc_preprocessor_res"),
    }
    return {k: v for k, v in fields.items() if v is not None}


def extract_blocks(data: dict) -> list[dict]:
    blocks: list[dict] = []
    for raw_page in _iter_pages(data):
        page = _get_page_result(raw_page)
        meta = _extract_page_meta(page)
        for item in page.get("parsing_res_list", []) or []:
            if not isinstance(item, dict):
                continue
            blocks.append({**meta, **item})
    return blocks


def extract_block_content(blocks: list[dict]) -> list[str]:
    out: list[str] = []
    for item in sorted(blocks, key=_order_key):
        text = item.get("block_content")
        if text:
            out.append(str(text))
    return out


def extract_spoken_blocks(blocks: list[dict]) -> list[str]:
    spoken: list[str] = []
    for item in sorted(blocks, key=_order_key):
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
    parser = argparse.ArgumentParser(description="Parse JSON and export ordered text outputs.")
    parser.add_argument(
        "--input",
        default="output/result.json",
        help="Input JSON path (default: output/result.json)",
    )
    parser.add_argument(
        "--out-dir",
        default="output",
        help="Output directory (default: output)",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        raise SystemExit(f"Missing input: {in_path}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(in_path.read_text(encoding="utf-8"))
    blocks = extract_blocks(data)
    block_texts = extract_block_content(blocks)
    spoken = extract_spoken_blocks(blocks)

    (out_dir / "parsed_blocks.json").write_text(
        json.dumps(blocks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "block_content.txt").write_text("\n\n".join(block_texts), encoding="utf-8")
    (out_dir / "block_content.json").write_text(
        json.dumps(block_texts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "spoken_output.txt").write_text("\n\n".join(spoken), encoding="utf-8")
    (out_dir / "spoken_output.json").write_text(
        json.dumps(spoken, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        "Saved parsed_blocks.json, block_content.txt/json, spoken_output.txt/json to "
        f"{out_dir} (blocks={len(blocks)}, spoken={len(spoken)})"
    )


if __name__ == "__main__":
    main()
