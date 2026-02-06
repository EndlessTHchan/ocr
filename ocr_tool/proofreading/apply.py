from __future__ import annotations

from pathlib import Path

from ..models import Block
from .deepseek import DeepSeekConfig, deepseek_proofread_blocks, deepseek_proofread_pages, load_deepseek_config_from_env


def _load_glossary(glossary_path: Path | None) -> list[str]:
    if not glossary_path:
        return []
    if not glossary_path.exists():
        return []
    items: list[str] = []
    for line in glossary_path.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if not t or t.startswith("#"):
            continue
        items.append(t)
    return items


def proofread_blocks_deepseek(
    *,
    page_id: int,
    blocks: list[Block],
    domain_hint: str = "",
    glossary_path: Path | None = None,
    max_chars_per_batch: int = 2400,
    max_blocks_per_batch: int = 6,
) -> dict:
    """Proofread blocks using DeepSeek. Returns debug metadata to attach to page JSON."""

    cfg: DeepSeekConfig = load_deepseek_config_from_env()
    glossary = _load_glossary(glossary_path)

    # Only proofread blocks that have text.
    candidates = [
        b
        for b in blocks
        if (b.raw_text or "").strip() and str(b.type.value) not in ("caption", "figure")
    ]
    debug = {
        "engine": "deepseek",
        "batches": 0,
        "glossary_items": len(glossary),
        "structure_hints": [],
    }

    def flush(batch: list[Block]) -> None:
        if not batch:
            return

        payload = [
            {
                "block_id": b.block_id,
                "text": (b.raw_text or ""),
                "bbox": list(b.bbox),
                "block_type": str(b.type.value),
            }
            for b in batch
        ]
        res = deepseek_proofread_blocks(
            cfg=cfg,
            page_id=page_id,
            blocks=payload,
            domain_hint=domain_hint,
            glossary=glossary,
        )

        by_id = {r.block_id: r for r in res.blocks}
        for b in batch:
            r = by_id.get(b.block_id)
            if not r:
                continue
            if b.raw_text_original is None:
                b.raw_text_original = b.raw_text
            b.raw_text = r.corrected_text
            b.role_suggestion = r.role_suggestion
            b.keep_recommendation = r.keep_recommendation
            b.keep_reason = r.keep_reason

        debug["batches"] = int(debug["batches"]) + 1
        debug.setdefault("meta", []).append(res.meta)
        # Append structured hints (block_id references stay local to page).
        for h in res.structure_hints:
            debug["structure_hints"].append(
                {
                    "block_id": h.block_id,
                    "kind": h.kind,
                    "level": h.level,
                    "text": h.text,
                    "confidence": h.confidence,
                    "reason": h.reason,
                }
            )

    current: list[Block] = []
    current_chars = 0
    for b in candidates:
        t = b.raw_text or ""
        # Batch by blocks and length.
        if current and (
            len(current) >= max_blocks_per_batch or (current_chars + len(t)) > max_chars_per_batch
        ):
            flush(current)
            current = []
            current_chars = 0
        current.append(b)
        current_chars += len(t)

    flush(current)
    return debug


def proofread_pages_deepseek(
    *,
    pages: list[tuple[int, list[Block]]],
    domain_hint: str = "",
    glossary_path: Path | None = None,
    max_chars_per_batch: int = 2400,
    max_blocks_per_batch: int = 60,
    max_pages_per_batch: int = 10,
) -> dict[int, dict]:
    """Proofread blocks across multiple pages in DeepSeek calls.

    This never sends images; it sends OCR text only (per project constraints).
    Returns per-page debug metadata.
    """

    cfg: DeepSeekConfig = load_deepseek_config_from_env()
    glossary = _load_glossary(glossary_path)

    debug_by_page: dict[int, dict] = {}
    for page_id, _blocks in pages:
        debug_by_page[page_id] = {
            "engine": "deepseek",
            "batches": 0,
            "glossary_items": len(glossary),
            "structure_hints": [],
            "meta": [],
        }

    # Build lookup for applying results.
    blocks_by_key: dict[tuple[int, str], Block] = {}
    candidates: list[tuple[int, Block]] = []
    for page_id, blocks in pages:
        for b in blocks:
            blocks_by_key[(page_id, b.block_id)] = b
            if (b.raw_text or "").strip() and str(b.type.value) not in ("caption", "figure"):
                candidates.append((page_id, b))

    def flush(batch_items: list[tuple[int, Block]]) -> None:
        if not batch_items:
            return

        pages_obj: dict[int, list[dict[str, str]]] = {}
        chars = 0
        for pid, b in batch_items:
            pages_obj.setdefault(pid, []).append(
                {
                    "block_id": b.block_id,
                    "text": (b.raw_text or ""),
                    "bbox": list(b.bbox),
                    "block_type": str(b.type.value),
                }
            )
            chars += len(b.raw_text or "")

        pages_payload = [{"page_id": pid, "blocks": blks} for pid, blks in pages_obj.items()]
        res = deepseek_proofread_pages(
            cfg=cfg,
            pages=pages_payload,
            domain_hint=domain_hint,
            glossary=glossary,
        )

        # Apply corrected text.
        for out_b in res.blocks:
            b = blocks_by_key.get((out_b.page_id, out_b.block_id))
            if not b:
                continue
            if b.raw_text_original is None:
                b.raw_text_original = b.raw_text
            b.raw_text = out_b.corrected_text
            b.role_suggestion = out_b.role_suggestion
            b.keep_recommendation = out_b.keep_recommendation
            b.keep_reason = out_b.keep_reason

        # Debug/meta + structure hints split by page.
        pages_in_req = sorted(pages_obj.keys())
        meta_entry = {
            **dict(res.meta),
            "pages": pages_in_req,
            "blocks": sum(len(v) for v in pages_obj.values()),
            "chars": chars,
        }

        for pid in pages_in_req:
            d = debug_by_page.get(pid)
            if d is None:
                continue
            d["batches"] = int(d.get("batches", 0)) + 1
            d.setdefault("meta", []).append(meta_entry)

        for h in res.structure_hints:
            d = debug_by_page.get(h.page_id)
            if d is None:
                continue
            d["structure_hints"].append(
                {
                    "block_id": h.block_id,
                    "kind": h.kind,
                    "level": h.level,
                    "text": h.text,
                    "confidence": h.confidence,
                    "reason": h.reason,
                }
            )

    # Pack candidates into DeepSeek requests.
    current: list[tuple[int, Block]] = []
    current_pages: set[int] = set()
    current_chars = 0
    for pid, b in candidates:
        t = b.raw_text or ""
        would_add_page = pid not in current_pages
        would_exceed_pages = would_add_page and (len(current_pages) >= max_pages_per_batch)
        would_exceed_blocks = current and (len(current) >= max_blocks_per_batch)
        would_exceed_chars = current and ((current_chars + len(t)) > max_chars_per_batch)

        if would_exceed_pages or would_exceed_blocks or would_exceed_chars:
            flush(current)
            current = []
            current_pages = set()
            current_chars = 0

        current.append((pid, b))
        current_pages.add(pid)
        current_chars += len(t)

    flush(current)
    return debug_by_page
