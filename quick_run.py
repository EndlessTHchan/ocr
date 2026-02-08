"""Quick-run entrypoint for the OCR pipeline.

Usage:
    python quick_run.py input.pdf --mode aistudio+deepseek
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from ocr_tool.models import FilterConfig, RunConfig
from ocr_tool.pipeline import run_pdf


DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "aistudio+deepseek",
    "outdir": "out",
    "dpi": 300,
    "include_page_markers": True,
    "page_batch_size": 20,
    "max_pages": None,
    "columns": "auto",
    "reading_direction": "auto",
    "language": "ch",
    "watermark_filter": False,
    "use_doc_orientation_classify": True,
    "use_doc_unwarping": True,
    "use_textline_orientation": True,
    "det_db_thresh": None,
    "det_db_box_thresh": None,
    "det_db_unclip_ratio": None,
    "rec_score_thresh": None,
    "vl_pipeline_version": "v1.5",
    "vl_model_dir": None,
    "vl_use_layout_detection": True,
    "aistudio_api_url": None,
    "aistudio_use_doc_orientation_classify": False,
    "aistudio_use_doc_unwarping": False,
    "aistudio_use_chart_recognition": False,
    "aistudio_timeout_s": 300,
    "proofread_domain_hint": "",
    "proofread_glossary_path": None,
    "proofread_max_chars_per_batch": 8000,
    "proofread_max_blocks_per_batch": 120,
    "proofread_max_pages_per_batch": 15,
    "filter": {
        "keep_header": False,
        "keep_footer": False,
        "keep_caption": False,
    },
    "post_process": True,
    "post_process_args": {
        "output": "out/output.cleaned.txt",
        "pages_per_batch": 8,
        "max_chars": 4000,
        "max_input_tokens": 3500,
        "max_output_tokens": 3072,
        "tokenizer_dir": "token",
    },
}


MODE_PRESETS: dict[str, dict[str, str]] = {
    "aistudio+deepseek": {"ocr_engine": "aistudio", "proofread_engine": "deepseek"},
    "aistudio+none": {"ocr_engine": "aistudio", "proofread_engine": "none"},
    "paddle+deepseek": {"ocr_engine": "paddle", "proofread_engine": "deepseek"},
    "paddle+none": {"ocr_engine": "paddle", "proofread_engine": "none"},
    "vl+deepseek": {"ocr_engine": "vl", "proofread_engine": "deepseek"},
    "vl+none": {"ocr_engine": "vl", "proofread_engine": "none"},
    "none": {"ocr_engine": "none", "proofread_engine": "none"},
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a JSON object: {path}")
    return data


def _apply_mode(cfg: dict[str, Any], mode: str) -> None:
    if not mode:
        return
    preset = MODE_PRESETS.get(mode)
    if preset:
        cfg.update(preset)
        return
    if "+" in mode:
        left, right = mode.split("+", 1)
        cfg["ocr_engine"] = left.strip()
        cfg["proofread_engine"] = right.strip()
        return
    raise SystemExit(f"Unknown mode: {mode}")


def _require_env_var(name: str, prompt: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    entered = getpass.getpass(prompt)
    if not entered:
        raise SystemExit(f"Missing {name}")
    os.environ[name] = entered
    return entered


def _resolve_api_keys(cfg: dict[str, Any], args: argparse.Namespace) -> None:
    if cfg.get("proofread_engine") == "deepseek":
        if args.deepseek_key:
            os.environ["DEEPSEEK_API_KEY"] = args.deepseek_key
        _require_env_var("DEEPSEEK_API_KEY", "Enter DeepSeek API key: ")

    if cfg.get("ocr_engine") == "aistudio":
        if args.aistudio_token:
            os.environ["AISTUDIO_TOKEN"] = args.aistudio_token
        _require_env_var("AISTUDIO_TOKEN", "Enter AIStudio token: ")


def _run_post_process(input_path: Path, cfg: dict[str, Any]) -> None:
    post_cfg = cfg.get("post_process_args", {}) if cfg.get("post_process") else None
    if not post_cfg:
        return

    output_path = Path(post_cfg.get("output", "out/output.cleaned.txt"))
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "post_process_output.py"),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--pages-per-batch",
        str(int(post_cfg.get("pages_per_batch", 8))),
        "--max-chars",
        str(int(post_cfg.get("max_chars", 4000))),
        "--max-input-tokens",
        str(int(post_cfg.get("max_input_tokens", 3500))),
        "--max-output-tokens",
        str(int(post_cfg.get("max_output_tokens", 3072))),
        "--tokenizer-dir",
        str(post_cfg.get("tokenizer_dir", "token")),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick-run OCR pipeline.")
    parser.add_argument("pdf", help="Input PDF path")
    parser.add_argument("--config", default="run_config.json", help="Config JSON path")
    parser.add_argument("--mode", default="", help="Mode preset, e.g. aistudio+deepseek")
    parser.add_argument("--outdir", default=None, help="Output directory (default from config)")
    parser.add_argument("--aistudio-token", default=None, help="AIStudio token (optional)")
    parser.add_argument("--deepseek-key", default=None, help="DeepSeek API key (optional)")
    parser.add_argument("--aistudio-api-url", default=None, help="AIStudio API URL (optional)")
    parser.add_argument("--no-post-process", action="store_true", help="Skip post-processing")
    args = parser.parse_args()

    load_dotenv()

    cfg = dict(DEFAULT_CONFIG)
    cfg.update(_load_json(Path(args.config)))

    if args.mode:
        cfg["mode"] = args.mode
    _apply_mode(cfg, cfg.get("mode", ""))

    if args.outdir:
        cfg["outdir"] = args.outdir
    if args.aistudio_api_url:
        cfg["aistudio_api_url"] = args.aistudio_api_url
    if args.no_post_process:
        cfg["post_process"] = False

    _resolve_api_keys(cfg, args)

    filter_cfg = cfg.get("filter", {})
    run_cfg = RunConfig(
        dpi=int(cfg.get("dpi", 300)),
        include_page_markers=bool(cfg.get("include_page_markers", True)),
        page_batch_size=int(cfg.get("page_batch_size", 20)),
        max_pages=cfg.get("max_pages"),
        columns=str(cfg.get("columns", "auto")),
        reading_direction=str(cfg.get("reading_direction", "auto")),
        language=str(cfg.get("language", "ch")),
        watermark_filter=bool(cfg.get("watermark_filter", False)),
        use_doc_orientation_classify=bool(cfg.get("use_doc_orientation_classify", True)),
        use_doc_unwarping=bool(cfg.get("use_doc_unwarping", True)),
        use_textline_orientation=bool(cfg.get("use_textline_orientation", True)),
        det_db_thresh=cfg.get("det_db_thresh"),
        det_db_box_thresh=cfg.get("det_db_box_thresh"),
        det_db_unclip_ratio=cfg.get("det_db_unclip_ratio"),
        rec_score_thresh=cfg.get("rec_score_thresh"),
        vl_pipeline_version=str(cfg.get("vl_pipeline_version", "v1.5")),
        vl_model_dir=cfg.get("vl_model_dir"),
        vl_use_layout_detection=bool(cfg.get("vl_use_layout_detection", True)),
        paddle_ocr_kwargs=cfg.get("paddle_ocr_kwargs", {}),
        aistudio_api_url=cfg.get("aistudio_api_url"),
        aistudio_token=os.getenv("AISTUDIO_TOKEN"),
        aistudio_use_doc_orientation_classify=bool(cfg.get("aistudio_use_doc_orientation_classify", False)),
        aistudio_use_doc_unwarping=bool(cfg.get("aistudio_use_doc_unwarping", False)),
        aistudio_use_chart_recognition=bool(cfg.get("aistudio_use_chart_recognition", False)),
        aistudio_timeout_s=int(cfg.get("aistudio_timeout_s", 300)),
        ocr_engine=str(cfg.get("ocr_engine", "none")),
        proofread_engine=str(cfg.get("proofread_engine", "none")),
        proofread_domain_hint=str(cfg.get("proofread_domain_hint", "")),
        proofread_glossary_path=cfg.get("proofread_glossary_path"),
        proofread_max_chars_per_batch=int(cfg.get("proofread_max_chars_per_batch", 8000)),
        proofread_max_blocks_per_batch=int(cfg.get("proofread_max_blocks_per_batch", 120)),
        proofread_max_pages_per_batch=int(cfg.get("proofread_max_pages_per_batch", 15)),
        filter=FilterConfig(
            keep_header=bool(filter_cfg.get("keep_header", False)),
            keep_footer=bool(filter_cfg.get("keep_footer", False)),
            keep_caption=bool(filter_cfg.get("keep_caption", False)),
        ),
    )

    pdf_path = Path(args.pdf)
    out_dir = Path(cfg.get("outdir", "out"))
    out_txt = run_pdf(pdf_path=pdf_path, out_dir=out_dir, cfg=run_cfg)

    if cfg.get("post_process"):
        _run_post_process(out_txt, cfg)


if __name__ == "__main__":
    main()
