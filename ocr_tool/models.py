from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class BlockType(str, Enum):
    header = "header"
    footer = "footer"
    title = "title"
    text = "text"
    table = "table"
    figure = "figure"
    caption = "caption"


BBox = tuple[int, int, int, int]


class Block(BaseModel):
    block_id: str
    type: BlockType
    bbox: BBox

    raw_text: str = ""
    raw_text_original: Optional[str] = None
    ocr_confidence: Optional[float] = None

    # LLM suggestions (never applied automatically unless user opts in)
    role_suggestion: Optional[str] = None
    keep_recommendation: Optional[str] = None
    keep_reason: Optional[str] = None


class PageImage(BaseModel):
    page_id: int
    image_path: str
    width: int
    height: int


class PageResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    page_id: int
    image_path: str
    blocks: list[Block]
    ordered_block_ids: list[str]


class FilterConfig(BaseModel):
    keep_header: bool = False
    keep_footer: bool = False
    keep_caption: bool = False
    keep_figure: bool = False


class RunConfig(BaseModel):
    dpi: int = Field(default=300, ge=72, le=600)
    include_page_markers: bool = True

    # Layout and ordering
    layout_strategy: Literal["simple"] = "simple"
    columns: Literal["auto", "single", "double"] = "auto"
    reading_direction: Literal["auto", "horizontal", "vertical_rtl"] = "auto"
    page_batch_size: int = 20
    max_pages: Optional[int] = None

    # Filtering
    filter: FilterConfig = Field(default_factory=FilterConfig)

    # OCR engine
    ocr_engine: Literal["none", "paddle", "vl", "aistudio"] = "none"
    language: str = "ch"
    watermark_filter: bool = False
    use_doc_orientation_classify: bool = True
    use_doc_unwarping: bool = True
    use_textline_orientation: bool = True
    det_db_thresh: Optional[float] = None
    det_db_box_thresh: Optional[float] = None
    det_db_unclip_ratio: Optional[float] = None
    rec_score_thresh: Optional[float] = None
    vl_pipeline_version: Literal["v1", "v1.5"] = "v1.5"
    vl_model_dir: Optional[str] = None
    vl_use_layout_detection: bool = True
    paddle_ocr_kwargs: dict[str, object] = Field(default_factory=dict)
    aistudio_api_url: Optional[str] = None
    aistudio_token: Optional[str] = None
    aistudio_use_doc_orientation_classify: bool = False
    aistudio_use_doc_unwarping: bool = False
    aistudio_use_chart_recognition: bool = False
    aistudio_timeout_s: int = 300

    # Proofreading (LLM)
    proofread_engine: Literal["none", "deepseek"] = "none"
    proofread_domain_hint: str = ""
    proofread_glossary_path: Optional[str] = None
    proofread_max_chars_per_batch: int = 8000
    proofread_max_blocks_per_batch: int = 120
    proofread_max_pages_per_batch: int = 20
