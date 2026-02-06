from __future__ import annotations

from ..models import Block, BlockType, FilterConfig


def keep_block(block: Block, cfg: FilterConfig) -> bool:
    # Hard requirements: captions / figures / page numbers are never kept.
    # (Blind-user friendly: remove non-body noise.)
    if block.type in (BlockType.caption, BlockType.figure):
        return False
    if (block.role_suggestion or "") in ("caption", "figure", "page_number"):
        return False

    if block.type == BlockType.header:
        return cfg.keep_header
    if block.type == BlockType.footer:
        return cfg.keep_footer
    return True


def filter_blocks_in_order(blocks: list[Block], ordered_ids: list[str], cfg: FilterConfig) -> list[Block]:
    by_id = {b.block_id: b for b in blocks}
    out: list[Block] = []
    for bid in ordered_ids:
        b = by_id.get(bid)
        if b is None:
            continue
        if keep_block(b, cfg):
            out.append(b)
    return out
