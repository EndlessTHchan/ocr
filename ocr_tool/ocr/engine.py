from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class OcrText:
    text: str
    confidence: float | None


class OcrEngine:
    def recognize(self, image: Image.Image) -> OcrText:
        raise NotImplementedError

    def recognize_page(self, image_path: str) -> OcrText:
        _ = image_path
        raise NotImplementedError


class NoneOcrEngine(OcrEngine):
    def recognize(self, image: Image.Image) -> OcrText:
        _ = image
        return OcrText(text="", confidence=None)

    def recognize_page(self, image_path: str) -> OcrText:
        _ = image_path
        return OcrText(text="", confidence=None)


def _strip_markdown(text: str) -> str:
    import re

    s = text or ""
    s = re.sub(r"!\[[^\]]*\]\([^\)]+\)", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


class PaddleOcrVlEngine(OcrEngine):
    def __init__(
        self,
        *,
        pipeline_version: str = "v1.5",
        model_dir: str | None = None,
        use_doc_orientation_classify: bool = True,
        use_doc_unwarping: bool = True,
        use_layout_detection: bool = True,
    ) -> None:
        try:
            from paddleocr import PaddleOCRVL  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "PaddleOCRVL not installed. Install extras: pip install \"paddleocr[doc-parser]\""
            ) from e

        kwargs: dict[str, object] = {
            "pipeline_version": pipeline_version,
            "use_doc_orientation_classify": use_doc_orientation_classify,
            "use_doc_unwarping": use_doc_unwarping,
            "use_layout_detection": use_layout_detection,
        }
        if model_dir:
            kwargs["vl_rec_model_dir"] = model_dir

        self._vl = PaddleOCRVL(**kwargs)

    def recognize(self, image: Image.Image) -> OcrText:
        _ = image
        return OcrText(text="", confidence=None)

    def recognize_page(self, image_path: str) -> OcrText:
        res_list = self._vl.predict(image_path)
        if not res_list:
            return OcrText(text="", confidence=None)
        res = res_list[0]

        markdown = None
        if hasattr(res, "_to_markdown"):
            try:
                markdown = res._to_markdown(pretty=False)
            except Exception:
                markdown = None
        if markdown is None and hasattr(res, "markdown"):
            try:
                markdown = res.markdown
            except Exception:
                markdown = None

        if isinstance(markdown, dict) and "markdown_texts" in markdown:
            return OcrText(text=_strip_markdown(str(markdown.get("markdown_texts", ""))), confidence=None)

        try:
            blocks = res["parsing_res_list"]
        except Exception:
            blocks = None

        if blocks:
            lines: list[str] = []
            for b in blocks:
                content = getattr(b, "content", None)
                if content:
                    lines.append(str(content).strip())
            return OcrText(text="\n\n".join([l for l in lines if l]), confidence=None)

        return OcrText(text="", confidence=None)


class PaddleOcrEngine(OcrEngine):
    def __init__(
        self,
        language: str = "ch",
        *,
        watermark_filter: bool = False,
        use_doc_orientation_classify: bool = True,
        use_doc_unwarping: bool = True,
        use_textline_orientation: bool = True,
        det_db_thresh: float | None = None,
        det_db_box_thresh: float | None = None,
        det_db_unclip_ratio: float | None = None,
        rec_score_thresh: float | None = None,
        paddle_ocr_kwargs: dict[str, object] | None = None,
    ) -> None:
        try:
            from paddleocr import PaddleOCR  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "PaddleOCR not installed. Install optional deps: pip install -r requirements-ocr.txt"
            ) from e

        self._watermark_filter = watermark_filter

        base_kwargs: dict[str, object] = {"lang": language}
        base_kwargs["use_doc_orientation_classify"] = use_doc_orientation_classify
        base_kwargs["use_doc_unwarping"] = use_doc_unwarping
        base_kwargs["use_textline_orientation"] = use_textline_orientation
        if det_db_thresh is not None:
            base_kwargs["det_db_thresh"] = det_db_thresh
        if det_db_box_thresh is not None:
            base_kwargs["det_db_box_thresh"] = det_db_box_thresh
        if det_db_unclip_ratio is not None:
            base_kwargs["det_db_unclip_ratio"] = det_db_unclip_ratio
        if rec_score_thresh is not None:
            base_kwargs["rec_score_thresh"] = rec_score_thresh

        if paddle_ocr_kwargs:
            base_kwargs.update(paddle_ocr_kwargs)

        # PaddleOCR has breaking changes across major versions.
        # - `use_angle_cls` is deprecated in >=3.x (use `use_textline_orientation`).
        # - Some versions don't accept `show_log`.
        init_errors: list[Exception] = []

        # Newer API (preferred)
        new_kwargs = dict(base_kwargs)
        new_kwargs_show = {**new_kwargs, "show_log": False}

        # Older API fallbacks
        old_kwargs = dict(base_kwargs)
        old_kwargs.pop("use_textline_orientation", None)
        if "use_angle_cls" not in old_kwargs:
            old_kwargs["use_angle_cls"] = use_textline_orientation
        old_kwargs_show = {**old_kwargs, "show_log": False}

        for kwargs in (new_kwargs_show, new_kwargs, old_kwargs_show, old_kwargs):
            try:
                self._ocr = PaddleOCR(**kwargs)
                init_errors = []
                break
            except Exception as e:  # pragma: no cover
                init_errors.append(e)

        if init_errors:
            # Raise the last error with context.
            raise init_errors[-1]

    def recognize(self, image: Image.Image) -> OcrText:
        import numpy as np
        import cv2

        arr = np.array(image.convert("RGB"))
        if self._watermark_filter:
            # Watermark suppression: detect low-contrast components and mask them out.
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            bg = cv2.medianBlur(gray, 21)
            contrast = cv2.absdiff(gray, bg)

            bw = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV,
                35,
                15,
            )

            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
            h, w = gray.shape[:2]
            img_area = float(h * w)
            min_area = max(200.0, img_area * 0.0005)
            low_contrast_thresh = 12.0
            large_area_ratio = 0.08
            low_fill_ratio = 0.15

            mask = np.zeros_like(gray, dtype=np.uint8)
            for i in range(1, num_labels):
                x, y, cw, ch, area = stats[i]
                if area < min_area:
                    continue
                roi = labels[y : y + ch, x : x + cw] == i
                mean_contrast = float(contrast[y : y + ch, x : x + cw][roi].mean())
                fill_ratio = float(area) / max(1.0, cw * ch)

                is_low_contrast = mean_contrast < low_contrast_thresh
                is_large_sparse = (area / img_area) > large_area_ratio and fill_ratio < low_fill_ratio
                if is_low_contrast or is_large_sparse:
                    mask[y : y + ch, x : x + cw][roi] = 255

            if mask.any():
                mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
                arr[mask > 0] = 255
        # PaddleOCR>=3.x may not accept `cls` (it can bubble into predict()).
        # We enable orientation at init when supported; here we keep the call minimal.
        result = self._ocr.ocr(arr)

        # PaddleOCR output can be [], None, [None], or [[...]] depending on input.
        if not result:
            return OcrText(text="", confidence=None)

        # Newer PaddleOCR (via PaddleX) may return a list of dicts with rec_texts/rec_scores.
        if isinstance(result, list) and result and isinstance(result[0], dict):
            rec_texts = result[0].get("rec_texts") or []
            rec_scores = result[0].get("rec_scores") or []
            texts = [t for t in rec_texts if t]
            confs = [float(c) for c in rec_scores[: len(rec_texts)] if isinstance(c, (int, float))]
            avg_conf = (sum(confs) / len(confs)) if confs else None
            return OcrText(text="\n".join(texts), confidence=avg_conf)

        iterable = result
        if isinstance(result, list):
            if len(result) == 0:
                return OcrText(text="", confidence=None)
            iterable = result[0]

        if not iterable:
            return OcrText(text="", confidence=None)

        lines: list[str] = []
        confs: list[float] = []
        for line in iterable:
            # paddleocr returns: [ [bbox], (text, conf) ]
            if not line or len(line) < 2:
                continue
            text_conf = line[1]
            if not text_conf or len(text_conf) < 2:
                continue
            text, conf = text_conf[0], float(text_conf[1])
            if text:
                lines.append(text)
                confs.append(conf)

        avg_conf = (sum(confs) / len(confs)) if confs else None
        return OcrText(text="\n".join(lines), confidence=avg_conf)


def build_engine(
    name: str,
    language: str,
    *,
    watermark_filter: bool = False,
    use_doc_orientation_classify: bool = True,
    use_doc_unwarping: bool = True,
    use_textline_orientation: bool = True,
    det_db_thresh: float | None = None,
    det_db_box_thresh: float | None = None,
    det_db_unclip_ratio: float | None = None,
    rec_score_thresh: float | None = None,
    vl_pipeline_version: str = "v1.5",
    vl_model_dir: str | None = None,
    vl_use_layout_detection: bool = True,
    paddle_ocr_kwargs: dict[str, object] | None = None,
) -> OcrEngine:
    if name == "none":
        return NoneOcrEngine()
    if name == "paddle":
        return PaddleOcrEngine(
            language=language,
            watermark_filter=watermark_filter,
            use_doc_orientation_classify=use_doc_orientation_classify,
            use_doc_unwarping=use_doc_unwarping,
            use_textline_orientation=use_textline_orientation,
            det_db_thresh=det_db_thresh,
            det_db_box_thresh=det_db_box_thresh,
            det_db_unclip_ratio=det_db_unclip_ratio,
            rec_score_thresh=rec_score_thresh,
            paddle_ocr_kwargs=paddle_ocr_kwargs,
        )
    if name == "vl":
        return PaddleOcrVlEngine(
            pipeline_version=vl_pipeline_version,
            model_dir=vl_model_dir,
            use_doc_orientation_classify=use_doc_orientation_classify,
            use_doc_unwarping=use_doc_unwarping,
            use_layout_detection=vl_use_layout_detection,
        )
    raise ValueError(f"Unknown OCR engine: {name}")


def crop_bbox(image: Image.Image, bbox: tuple[int, int, int, int]) -> Image.Image:
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(x1, image.width))
    x2 = max(0, min(x2, image.width))
    y1 = max(0, min(y1, image.height))
    y2 = max(0, min(y2, image.height))
    if x2 <= x1 or y2 <= y1:
        return image
    return image.crop((x1, y1, x2, y2))
