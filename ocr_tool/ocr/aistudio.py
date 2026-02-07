"""AIStudio PaddleOCR API client and result parsing."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import Block, BlockType

import requests

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


@dataclass(frozen=True)
class AIStudioConfig:
    api_url: str
    token: str
    use_doc_orientation_classify: bool = False
    use_doc_unwarping: bool = False
    use_chart_recognition: bool = False
    timeout_s: int = 300


def load_aistudio_config_from_env() -> AIStudioConfig:
    api_url = os.getenv("AISTUDIO_API_URL", "https://bbe186c9acy0c7aa.aistudio-app.com/layout-parsing")
    token = os.getenv("AISTUDIO_TOKEN")
    if not token:
        raise RuntimeError("Missing AISTUDIO_TOKEN in environment/.env")
    return AIStudioConfig(api_url=api_url, token=token)


def _guess_file_type(path: Path) -> int:
    return 0 if path.suffix.lower() == ".pdf" else 1


def _normalize_text(text: str) -> str:
    s = text.replace("\r\n", "\n").replace("\r", "\n")
    while "\n\n\n" in s:
        s = s.replace("\n\n\n", "\n\n")
    return s.strip()


def _order_key(item: dict[str, Any]) -> tuple[int, int]:
    order = item.get("block_order")
    block_id = item.get("block_id")
    order_val = int(order) if isinstance(order, int) else 1_000_000
    id_val = int(block_id) if isinstance(block_id, int) else 1_000_000
    return (order_val, id_val)


def _parse_bbox(bbox: Any, page_width: int, page_height: int) -> tuple[int, int, int, int]:
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        try:
            x1, y1, x2, y2 = bbox[:4]
            return (int(x1), int(y1), int(x2), int(y2))
        except Exception:
            return (0, 0, page_width, page_height)
    return (0, 0, page_width, page_height)


def _map_block_type(label: str) -> BlockType:
    if label in TITLE_LABELS:
        return BlockType.title
    if label == "table":
        return BlockType.table
    if label == "figure":
        return BlockType.figure
    if label == "caption":
        return BlockType.caption
    if label == "header":
        return BlockType.header
    if label == "footer":
        return BlockType.footer
    return BlockType.text


def build_blocks_from_aistudio_result(
    result: dict[str, Any], page_width: int, page_height: int
) -> tuple[list[Block], list[str]]:
    pages = result.get("layoutParsingResults")
    if not isinstance(pages, list) or not pages:
        return ([], [])

    page = pages[0]
    pruned = page.get("prunedResult") if isinstance(page, dict) else None
    if isinstance(pruned, dict):
        items = pruned.get("parsing_res_list", [])
    elif isinstance(page, dict):
        items = page.get("parsing_res_list", [])
    else:
        items = []

    blocks: list[Block] = []
    ordered_ids: list[str] = []

    if not isinstance(items, list):
        return ([], [])

    order_tuples: list[tuple[int, int, str]] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        raw_id = item.get("block_id")
        block_id = f"a{raw_id}" if raw_id is not None else f"a{idx}"
        label = str(item.get("block_label") or "")
        bbox = _parse_bbox(item.get("block_bbox"), page_width, page_height)
        text = str(item.get("block_content") or "")
        blocks.append(
            Block(
                block_id=block_id,
                type=_map_block_type(label),
                bbox=bbox,
                raw_text=text,
            )
        )
        order_val, id_val = _order_key(item)
        order_tuples.append((order_val, id_val, block_id))

    ordered_ids = [bid for _, _, bid in sorted(order_tuples)]
    return (blocks, ordered_ids)


def extract_spoken_blocks(result: dict[str, Any]) -> list[str]:
    spoken: list[str] = []
    for page in result.get("layoutParsingResults", []):
        pruned = page.get("prunedResult", {})
        items = pruned.get("parsing_res_list", [])

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


def call_aistudio_api(path: Path, cfg: AIStudioConfig) -> dict[str, Any]:
    file_bytes = path.read_bytes()
    file_data = base64.b64encode(file_bytes).decode("ascii")

    payload = {
        "file": file_data,
        "fileType": _guess_file_type(path),
        "useDocOrientationClassify": cfg.use_doc_orientation_classify,
        "useDocUnwarping": cfg.use_doc_unwarping,
        "useChartRecognition": cfg.use_chart_recognition,
    }

    headers = {
        "Authorization": f"token {cfg.token}",
        "Content-Type": "application/json",
    }

    resp = requests.post(cfg.api_url, json=payload, headers=headers, timeout=cfg.timeout_s)
    resp.raise_for_status()
    data = resp.json()
    if "result" not in data:
        raise RuntimeError(f"Unexpected API response: {json.dumps(data)[:500]}")
    return data["result"]
