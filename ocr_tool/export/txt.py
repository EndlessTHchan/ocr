from __future__ import annotations

from pathlib import Path

from ..models import Block, PageResult


def export_txt(pages: list[PageResult], out_path: Path, include_page_markers: bool) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        for page in pages:
            if include_page_markers:
                f.write(f"【原书第 {page.page_id} 页】\n")

            by_id = {b.block_id: b for b in page.blocks}
            for bid in page.ordered_block_ids:
                b = by_id.get(bid)
                if not b:
                    continue
                text = (b.raw_text or "").strip()
                if text:
                    f.write(text)
                    f.write("\n\n")

            f.write("\n")
