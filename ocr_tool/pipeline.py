from __future__ import annotations

from pathlib import Path

from PIL import Image

from .export.txt import export_txt
from .filtering.apply import filter_blocks_in_order
from .layout.simple import analyze_page_simple
from .models import PageResult, RunConfig
from .ocr.engine import build_engine, crop_bbox
from .proofreading.apply import proofread_blocks_deepseek, proofread_pages_deepseek
from .ordering.column_detect import detect_double_column, detect_vertical_rtl_columns
from .ordering.rules import (
    order_blocks_auto,
    order_blocks_double_column_with_header_footer,
    order_blocks_vertical_rtl_with_header_footer,
    order_blocks_single_column,
)
from .pdf_splitter import split_pdf_to_images
from .utils.paths import ensure_dir


def run_pdf(pdf_path: Path, out_dir: Path, cfg: RunConfig) -> Path:
    """Run the full pipeline for a scanned PDF and export a TXT.

    Artifacts (debuggable):
    - out_dir/pages/0001.png
    - out_dir/pages/0001.json
    - out_dir/output.txt
    """

    out_dir = ensure_dir(out_dir)
    pages_dir = ensure_dir(out_dir / "pages")

    page_images = split_pdf_to_images(pdf_path=pdf_path, out_dir=pages_dir, dpi=cfg.dpi)
    engine = build_engine(
        cfg.ocr_engine,
        cfg.language,
        watermark_filter=cfg.watermark_filter,
        use_doc_orientation_classify=cfg.use_doc_orientation_classify,
        use_doc_unwarping=cfg.use_doc_unwarping,
        use_textline_orientation=cfg.use_textline_orientation,
        det_db_thresh=cfg.det_db_thresh,
        det_db_box_thresh=cfg.det_db_box_thresh,
        det_db_unclip_ratio=cfg.det_db_unclip_ratio,
        rec_score_thresh=cfg.rec_score_thresh,
        paddle_ocr_kwargs=cfg.paddle_ocr_kwargs,
        vl_pipeline_version=cfg.vl_pipeline_version,
        vl_model_dir=cfg.vl_model_dir,
        vl_use_layout_detection=cfg.vl_use_layout_detection,
    )

    results: list[PageResult] = []

    def write_page_json(page_result: PageResult, *, column_detect: dict | None, proofread: dict | None) -> None:
        payload = page_result.model_dump()
        if column_detect is not None:
            payload["column_detect"] = column_detect
        if proofread is not None:
            payload["proofread"] = proofread
        (pages_dir / f"{page_result.page_id:04d}.json").write_text(
            __import__("json").dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    pending_pages: list[PageResult] = []
    pending_column_debug: dict[int, dict] = {}

    for page in page_images:
        layout = analyze_page_simple(page)
        blocks = layout.blocks

        # Baseline layout outputs 3 blocks: header/body/footer.
        # Column split and vertical detection are applied on the body block only.
        split_x: int | None = None
        double_debug: dict | None = None
        vertical_debug: dict | None = None

        body_bbox = None
        for b in blocks:
            if b.block_id == "b2":
                body_bbox = b.bbox
                break

        vertical_columns: list[tuple[int, int]] = []
        if cfg.reading_direction in ("auto", "vertical_rtl"):
            vdet = detect_vertical_rtl_columns(page.image_path, body_bbox)
            vertical_debug = vdet.debug
            if cfg.reading_direction == "vertical_rtl":
                if not vdet.is_vertical:
                    vertical_debug = {**vdet.debug, "forced": True}
                if vdet.columns:
                    vertical_columns = vdet.columns
                elif body_bbox is not None:
                    vertical_columns = [(body_bbox[0], body_bbox[2])]
            elif vdet.is_vertical:
                vertical_columns = vdet.columns

        if vertical_columns:
            new_blocks = []
            for b in blocks:
                if b.block_id == "b2":
                    x1, y1, x2, y2 = b.bbox
                    for idx, (cx1, cx2) in enumerate(vertical_columns, start=1):
                        left = max(x1, cx1)
                        right = min(x2, cx2)
                        if right <= left:
                            continue
                        new_blocks.append(
                            b.model_copy(update={"block_id": f"b2v{idx}", "bbox": (left, y1, right, y2)})
                        )
                    continue
                new_blocks.append(b)
            blocks = new_blocks
        else:
            if cfg.columns == "double":
                split_x = page.width // 2
                double_debug = {"forced": True, "split_x": split_x}
            elif cfg.columns == "auto":
                det = detect_double_column(page.image_path, body_bbox)
                double_debug = det.debug
                split_x = det.split_x if det.is_double else None

            if split_x is not None:
                new_blocks = []
                for b in blocks:
                    if b.block_id == "b2":
                        x1, y1, x2, y2 = b.bbox
                        # Only split if it meaningfully spans both sides.
                        if x1 < split_x < x2 and (x2 - x1) > int(page.width * 0.6):
                            left_bbox = (x1, y1, split_x, y2)
                            right_bbox = (split_x, y1, x2, y2)
                            new_blocks.append(b.model_copy(update={"block_id": "b2l", "bbox": left_bbox}))
                            new_blocks.append(b.model_copy(update={"block_id": "b2r", "bbox": right_bbox}))
                            continue
                    new_blocks.append(b)
                blocks = new_blocks

        if vertical_columns:
            ordered_ids = order_blocks_vertical_rtl_with_header_footer(blocks)
        elif cfg.columns == "single":
            ordered_ids = order_blocks_single_column(blocks)
        elif split_x is not None:
            ordered_ids = order_blocks_double_column_with_header_footer(blocks, split_x=split_x)
        else:
            ordered_ids = order_blocks_auto(blocks, page_width=page.width)

        if hasattr(engine, "recognize_page") and cfg.ocr_engine == "vl":
            ocr_out = engine.recognize_page(page.image_path)
            for b in blocks:
                if b.block_id == "b2":
                    b.raw_text = ocr_out.text
                    b.ocr_confidence = ocr_out.confidence
                else:
                    b.raw_text = ""
                    b.ocr_confidence = None
        else:
            with Image.open(page.image_path) as im:
                im = im.convert("RGB")
                for b in blocks:
                    cropped = crop_bbox(im, b.bbox)
                    ocr_out = engine.recognize(cropped)
                    b.raw_text = ocr_out.text
                    b.ocr_confidence = ocr_out.confidence

        filtered_blocks = filter_blocks_in_order(blocks, ordered_ids, cfg.filter)
        filtered_ids = [b.block_id for b in filtered_blocks]

        page_result = PageResult(
            page_id=page.page_id,
            image_path=page.image_path,
            blocks=filtered_blocks,
            ordered_block_ids=filtered_ids,
        )

        results.append(page_result)

        layout_debug: dict | None = None
        if vertical_debug or double_debug:
            layout_debug = {
                "vertical": vertical_debug,
                "double": double_debug,
            }

        # If DeepSeek is enabled, buffer pages and proofread in page-batches.
        if cfg.proofread_engine == "deepseek":
            pending_pages.append(page_result)
            if layout_debug is not None:
                pending_column_debug[page_result.page_id] = layout_debug

            if len(pending_pages) >= max(1, int(cfg.proofread_max_pages_per_batch)):
                from pathlib import Path

                glossary_path = Path(cfg.proofread_glossary_path) if cfg.proofread_glossary_path else None
                debug_by_page = proofread_pages_deepseek(
                    pages=[(p.page_id, p.blocks) for p in pending_pages],
                    domain_hint=cfg.proofread_domain_hint,
                    glossary_path=glossary_path,
                    max_chars_per_batch=cfg.proofread_max_chars_per_batch,
                    max_blocks_per_batch=cfg.proofread_max_blocks_per_batch,
                    max_pages_per_batch=cfg.proofread_max_pages_per_batch,
                )

                for p in pending_pages:
                    # After LLM, apply filtering again using role_suggestion.
                    p.blocks = filter_blocks_in_order(p.blocks, p.ordered_block_ids, cfg.filter)
                    p.ordered_block_ids = [b.block_id for b in p.blocks]
                    write_page_json(
                        p,
                        column_detect=pending_column_debug.get(p.page_id),
                        proofread=debug_by_page.get(p.page_id),
                    )

                pending_pages = []
                pending_column_debug = {}
        else:
            # No LLM: write page JSON immediately.
            write_page_json(page_result, column_detect=layout_debug, proofread=None)

    # Flush remaining pending pages for DeepSeek mode.
    if cfg.proofread_engine == "deepseek" and pending_pages:
        from pathlib import Path

        glossary_path = Path(cfg.proofread_glossary_path) if cfg.proofread_glossary_path else None
        debug_by_page = proofread_pages_deepseek(
            pages=[(p.page_id, p.blocks) for p in pending_pages],
            domain_hint=cfg.proofread_domain_hint,
            glossary_path=glossary_path,
            max_chars_per_batch=cfg.proofread_max_chars_per_batch,
            max_blocks_per_batch=cfg.proofread_max_blocks_per_batch,
            max_pages_per_batch=cfg.proofread_max_pages_per_batch,
        )
        for p in pending_pages:
            p.blocks = filter_blocks_in_order(p.blocks, p.ordered_block_ids, cfg.filter)
            p.ordered_block_ids = [b.block_id for b in p.blocks]
            write_page_json(
                p,
                column_detect=pending_column_debug.get(p.page_id),
                proofread=debug_by_page.get(p.page_id),
            )

    out_txt = out_dir / "output.txt"
    export_txt(results, out_txt, include_page_markers=cfg.include_page_markers)
    return out_txt
