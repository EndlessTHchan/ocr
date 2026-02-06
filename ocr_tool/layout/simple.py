from __future__ import annotations

from .types import LayoutResult
from ..models import Block, BlockType, PageImage


def analyze_page_simple(page: PageImage) -> LayoutResult:
    """Baseline, fully deterministic layout:

    - Always returns 3 blocks: header (top 8%), body (middle), footer (bottom 8%).
    - Does NOT delete anything. Filtering happens later.

    This is intentionally simple so the pipeline can run end-to-end and be debugged.
    """

    h = page.height
    w = page.width

    header_h = max(1, int(h * 0.08))
    footer_h = max(1, int(h * 0.08))

    blocks = [
        Block(block_id="b1", type=BlockType.header, bbox=(0, 0, w, header_h)),
        Block(block_id="b2", type=BlockType.text, bbox=(0, header_h, w, h - footer_h)),
        Block(block_id="b3", type=BlockType.footer, bbox=(0, h - footer_h, w, h)),
    ]

    return LayoutResult(blocks=blocks)
