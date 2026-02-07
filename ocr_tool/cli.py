from __future__ import annotations

from pathlib import Path
import json

import typer
from dotenv import load_dotenv
from rich.console import Console

from .models import FilterConfig, RunConfig
from .pipeline import run_pdf

app = typer.Typer(add_completion=False, help="Scan PDF → TXT (accessible-first).")
console = Console()


@app.command()
def doctor() -> None:
    """Print basic environment info for debugging."""

    import sys

    console.print(f"Python: {sys.version.split()[0]}")
    console.print(f"Executable: {sys.executable}")


@app.command()
def run(
    pdf: Path = typer.Argument(..., exists=True, dir_okay=False, help="Input scanned PDF path"),
    outdir: Path = typer.Option(Path("out"), help="Output directory"),
    dpi: int = typer.Option(300, help="Render DPI (72-600)", min=72, max=600),
    ocr_engine: str = typer.Option(
        "none", help="OCR engine: none|paddle|vl|aistudio"
    ),
    keep_header: bool = typer.Option(False, help="Keep header blocks"),
    keep_footer: bool = typer.Option(False, help="Keep footer blocks"),
    keep_caption: bool = typer.Option(False, help="Keep caption blocks"),
    include_page_markers: bool = typer.Option(True, help="Insert 【原书第 N 页】 markers"),
    page_batch_size: int = typer.Option(
        20,
        help="Process pages in batches (default 20)",
        min=1,
        max=200,
    ),
    max_pages: int | None = typer.Option(
        None,
        help="Limit total pages to process (default: all)",
        min=1,
        max=2000,
    ),
    columns: str = typer.Option(
        "auto",
        help="Reading order columns: auto|single|double",
    ),
    reading_direction: str = typer.Option(
        "auto",
        help="Reading direction: auto|horizontal|vertical_rtl",
    ),
    watermark_filter: bool = typer.Option(
        False,
        help="Apply watermark suppression pre-processing before OCR",
    ),
    use_doc_orientation_classify: bool = typer.Option(
        True,
        help="Use document orientation classification module",
    ),
    use_doc_unwarping: bool = typer.Option(
        True,
        help="Use document unwarping module",
    ),
    use_textline_orientation: bool = typer.Option(
        True,
        help="Use textline orientation classification module",
    ),
    det_db_thresh: float | None = typer.Option(
        None,
        help="Text detection threshold (det_db_thresh)",
    ),
    det_db_box_thresh: float | None = typer.Option(
        None,
        help="Text detection box threshold (det_db_box_thresh)",
    ),
    det_db_unclip_ratio: float | None = typer.Option(
        None,
        help="Text detection unclip ratio (det_db_unclip_ratio)",
    ),
    rec_score_thresh: float | None = typer.Option(
        None,
        help="Text recognition score threshold (rec_score_thresh)",
    ),
    vl_pipeline_version: str = typer.Option(
        "v1.5",
        help="PaddleOCR-VL pipeline version: v1|v1.5",
    ),
    vl_model_dir: Path | None = typer.Option(
        None,
        help="Local PaddleOCR-VL model dir (downloaded from AIStudio)",
        exists=False,
        dir_okay=True,
    ),
    vl_use_layout_detection: bool = typer.Option(
        True,
        help="Use layout detection in PaddleOCR-VL",
    ),
    paddle_ocr_config: Path | None = typer.Option(
        None,
        help="Optional JSON file with PaddleOCR init kwargs",
        exists=False,
        dir_okay=False,
    ),
    aistudio_api_url: str | None = typer.Option(
        None,
        help="AIStudio OCR API URL (default from AISTUDIO_API_URL)",
    ),
    aistudio_token: str | None = typer.Option(
        None,
        help="AIStudio OCR API token (default from AISTUDIO_TOKEN)",
    ),
    aistudio_use_doc_orientation_classify: bool = typer.Option(
        False,
        help="AIStudio: use document orientation classification",
    ),
    aistudio_use_doc_unwarping: bool = typer.Option(
        False,
        help="AIStudio: use document unwarping",
    ),
    aistudio_use_chart_recognition: bool = typer.Option(
        False,
        help="AIStudio: use chart recognition",
    ),
    aistudio_timeout_s: int = typer.Option(
        300,
        help="AIStudio: request timeout in seconds",
    ),
    language: str = typer.Option("ch", help="OCR language (paddleocr lang code), e.g. ch"),
    proofread_engine: str = typer.Option(
        "none",
        help="Proofreading engine (LLM): none|deepseek. DeepSeek only does minimal OCR correction and outputs strict JSON.",
    ),
    proofread_domain_hint: str = typer.Option(
        "",
        help="Optional domain hint for proofreading, e.g. '考研政治'.",
    ),
    proofread_glossary: Path | None = typer.Option(
        None,
        help="Optional glossary file (one term per line).",
        exists=False,
        dir_okay=False,
    ),
    proofread_max_chars: int = typer.Option(8000, help="Max chars per DeepSeek batch", min=200, max=8000),
    proofread_max_blocks: int = typer.Option(120, help="Max blocks per DeepSeek batch/request", min=1, max=200),
    proofread_pages: int = typer.Option(
        15,
        help="Max pages per DeepSeek batch/request (default 15)",
        min=1,
        max=50,
    ),
):
    """Run the pipeline and export TXT.

        Minimal install (no OCR):
            .\.venv\Scripts\python.exe -m pip install -r requirements.txt
            .\.venv\Scripts\python.exe -m ocr_tool.cli run your.pdf --ocr-engine none

        With OCR (recommended):
            .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-ocr.txt
            .\.venv\Scripts\python.exe -m ocr_tool.cli run your.pdf --ocr-engine paddle
    """

    load_dotenv()  # loads .env if present; keys are not printed

    extra_kwargs: dict[str, object] = {}
    if paddle_ocr_config:
        try:
            raw = paddle_ocr_config.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                extra_kwargs = data
            else:
                raise ValueError("PaddleOCR config JSON must be an object")
        except Exception as e:
            console.print(f"[red]ERROR[/red]: invalid paddle_ocr_config: {e}")
            raise typer.Exit(code=1)

    cfg = RunConfig(
        dpi=dpi,
        include_page_markers=include_page_markers,
        page_batch_size=page_batch_size,
        max_pages=max_pages,
        columns=columns,  # type: ignore[arg-type]

        reading_direction=reading_direction,  # type: ignore[arg-type]
        language=language,
        watermark_filter=watermark_filter,
        use_doc_orientation_classify=use_doc_orientation_classify,
        use_doc_unwarping=use_doc_unwarping,
        use_textline_orientation=use_textline_orientation,
        det_db_thresh=det_db_thresh,
        det_db_box_thresh=det_db_box_thresh,
        det_db_unclip_ratio=det_db_unclip_ratio,
        rec_score_thresh=rec_score_thresh,
        vl_pipeline_version=vl_pipeline_version,  # type: ignore[arg-type]
        vl_model_dir=str(vl_model_dir) if vl_model_dir else None,
        vl_use_layout_detection=vl_use_layout_detection,
        paddle_ocr_kwargs=extra_kwargs,
        aistudio_api_url=aistudio_api_url,
        aistudio_token=aistudio_token,
        aistudio_use_doc_orientation_classify=aistudio_use_doc_orientation_classify,
        aistudio_use_doc_unwarping=aistudio_use_doc_unwarping,
        aistudio_use_chart_recognition=aistudio_use_chart_recognition,
        aistudio_timeout_s=aistudio_timeout_s,
        ocr_engine=ocr_engine,  # type: ignore[arg-type]
        proofread_engine=proofread_engine,  # type: ignore[arg-type]
        proofread_domain_hint=proofread_domain_hint,
        proofread_glossary_path=str(proofread_glossary) if proofread_glossary else None,
        proofread_max_chars_per_batch=proofread_max_chars,
        proofread_max_blocks_per_batch=proofread_max_blocks,
        proofread_max_pages_per_batch=proofread_pages,
        filter=FilterConfig(
            keep_header=keep_header,
            keep_footer=keep_footer,
            keep_caption=keep_caption,
        ),
    )

    console.print(f"[bold]PDF[/bold]: {pdf}")
    console.print(f"[bold]Out[/bold]: {outdir}")
    console.print(f"[bold]DPI[/bold]: {cfg.dpi} | [bold]OCR[/bold]: {cfg.ocr_engine} | [bold]Columns[/bold]: {cfg.columns}")

    try:
        out_txt = run_pdf(pdf_path=pdf, out_dir=outdir, cfg=cfg)
    except Exception as e:
        console.print(f"[red]ERROR[/red]: {e}")
        raise typer.Exit(code=1)

    console.print(f"[green]OK[/green] Exported: {out_txt}")


if __name__ == "__main__":
    app()
