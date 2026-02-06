from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class ColumnDetectResult:
    is_double: bool
    split_x: int | None
    debug: dict


@dataclass(frozen=True)
class VerticalDetectResult:
    is_vertical: bool
    columns: list[tuple[int, int]]
    debug: dict


def _smooth(values: list[float], window: int) -> list[float]:
    if window <= 1 or len(values) <= 2:
        return values
    half = window // 2
    out: list[float] = []
    for i in range(len(values)):
        s = 0.0
        c = 0
        for j in range(max(0, i - half), min(len(values), i + half + 1)):
            s += values[j]
            c += 1
        out.append(s / max(1, c))
    return out


def _find_bands(values: list[float], *, threshold: float, min_width: int) -> list[tuple[int, int]]:
    bands: list[tuple[int, int]] = []
    in_band = False
    start = 0
    for i, v in enumerate(values):
        if v >= threshold and not in_band:
            in_band = True
            start = i
        elif v < threshold and in_band:
            end = i - 1
            if (end - start + 1) >= min_width:
                bands.append((start, end))
            in_band = False
    if in_band:
        end = len(values) - 1
        if (end - start + 1) >= min_width:
            bands.append((start, end))
    return bands


def detect_double_column(
    image_path: str | Path,
    body_bbox: tuple[int, int, int, int] | None,
    *,
    downsample_width: int = 420,
    center_band: tuple[float, float] = (0.35, 0.65),
    min_side_ink: float = 0.010,
    max_valley_ratio: float = 0.75,
    min_balance_ratio: float = 0.55,
) -> ColumnDetectResult:
    """Detect whether a page is likely double-column.

    Deterministic, debug-friendly heuristic:
    - Crop to body bbox (exclude header/footer if provided)
    - Downsample
    - Compute vertical ink density projection
    - Find a low-ink valley near center

    Returns split_x in ORIGINAL IMAGE coordinates.
    """

    image_path = Path(image_path)
    debug: dict = {
        "image": str(image_path),
        "downsample_width": downsample_width,
    }

    with Image.open(image_path) as im:
        im = im.convert("L")
        if body_bbox is not None:
            x1, y1, x2, y2 = body_bbox
            x1 = max(0, min(x1, im.width))
            x2 = max(0, min(x2, im.width))
            y1 = max(0, min(y1, im.height))
            y2 = max(0, min(y2, im.height))
            if x2 > x1 and y2 > y1:
                im = im.crop((x1, y1, x2, y2))

        orig_w, orig_h = im.size

        if orig_w < 200 or orig_h < 200:
            return ColumnDetectResult(False, None, {**debug, "reason": "image too small"})

        scale = downsample_width / float(orig_w)
        new_w = max(120, int(orig_w * scale))
        new_h = max(120, int(orig_h * scale))
        im_small = im.resize((new_w, new_h))

    # Use numpy if present; otherwise fall back to Python loops.
    try:
        import numpy as np

        arr = np.array(im_small, dtype=np.uint8)
        white = float(np.percentile(arr, 90))
        thresh = int(max(80, min(230, white - 40)))
        ink = arr < thresh
        col_density = (ink.sum(axis=0) / max(1, ink.shape[0])).astype(float).tolist()
        debug.update({"threshold": thresh, "white_p90": white, "engine": "numpy"})
    except Exception:
        px = list(im_small.getdata())  # row-major
        # Rough threshold based on bright percentile proxy.
        # (Avoid heavy stats; scanned docs are usually high-contrast.)
        sample = px[:: max(1, len(px) // 20000)]
        sample_sorted = sorted(sample)
        white = float(sample_sorted[int(len(sample_sorted) * 0.90)]) if sample_sorted else 255.0
        thresh = int(max(80, min(230, white - 40)))
        w, h = im_small.size
        counts = [0] * w
        for i, v in enumerate(px):
            if v < thresh:
                counts[i % w] += 1
        col_density = [c / float(h) for c in counts]
        debug.update({"threshold": thresh, "white_p90": white, "engine": "python"})

    col_density = _smooth(col_density, window=15)

    w = len(col_density)
    lo = int(w * center_band[0])
    hi = int(w * center_band[1])
    if hi - lo < 20:
        return ColumnDetectResult(False, None, {**debug, "reason": "center band too narrow"})

    # Find valley (minimum ink density) near the center.
    min_idx = min(range(lo, hi), key=lambda i: col_density[i])
    valley = col_density[min_idx]

    pad = 10
    left_slice = col_density[: max(lo, min_idx - pad)]
    right_slice = col_density[min(min_idx + pad, hi) :]
    if not left_slice or not right_slice:
        return ColumnDetectResult(False, None, {**debug, "reason": "insufficient sides"})

    left_mean = sum(left_slice) / len(left_slice)
    right_mean = sum(right_slice) / len(right_slice)
    min_side = min(left_mean, right_mean)
    max_side = max(left_mean, right_mean)
    balance = (min_side / max_side) if max_side > 0 else 0.0

    debug.update(
        {
            "valley": valley,
            "left_mean": left_mean,
            "right_mean": right_mean,
            "balance": balance,
            "min_idx": min_idx,
            "w_small": w,
        }
    )

    if left_mean < min_side_ink or right_mean < min_side_ink:
        return ColumnDetectResult(False, None, {**debug, "reason": "one side too empty"})

    if min_side <= 0:
        return ColumnDetectResult(False, None, {**debug, "reason": "invalid side density"})

    if balance < min_balance_ratio:
        return ColumnDetectResult(False, None, {**debug, "reason": "sides unbalanced"})

    if valley > max_valley_ratio * min_side:
        return ColumnDetectResult(False, None, {**debug, "reason": "no strong center valley"})

    # Map split_x back to original coordinates of the (cropped) image.
    split_x_cropped = int(round((min_idx / max(1, w)) * orig_w))

    if split_x_cropped < int(orig_w * 0.25) or split_x_cropped > int(orig_w * 0.75):
        return ColumnDetectResult(False, None, {**debug, "reason": "split too close to edge"})

    # If we cropped, add offset back.
    if body_bbox is not None:
        x1, _, _, _ = body_bbox
        split_x = x1 + split_x_cropped
    else:
        split_x = split_x_cropped

    return ColumnDetectResult(True, split_x, debug)


def detect_vertical_rtl_columns(
    image_path: str | Path,
    body_bbox: tuple[int, int, int, int] | None,
    *,
    downsample_width: int = 420,
    min_columns: int = 3,
    min_band_width_ratio: float = 0.03,
    max_band_width_ratio: float = 0.18,
    min_ink_ratio: float = 0.012,
) -> VerticalDetectResult:
    """Detect vertical (right-to-left) columns and return column x-ranges.

    Heuristic (conservative):
    - Crop to body bbox if provided
    - Downsample
    - Compute vertical ink density
    - Find multiple narrow bands across width (>= min_columns)
    """

    image_path = Path(image_path)
    debug: dict = {
        "image": str(image_path),
        "downsample_width": downsample_width,
        "min_columns": min_columns,
    }

    with Image.open(image_path) as im:
        im = im.convert("L")
        if body_bbox is not None:
            x1, y1, x2, y2 = body_bbox
            x1 = max(0, min(x1, im.width))
            x2 = max(0, min(x2, im.width))
            y1 = max(0, min(y1, im.height))
            y2 = max(0, min(y2, im.height))
            if x2 > x1 and y2 > y1:
                im = im.crop((x1, y1, x2, y2))

        orig_w, orig_h = im.size
        if orig_w < 200 or orig_h < 200:
            return VerticalDetectResult(False, [], {**debug, "reason": "image too small"})

        scale = downsample_width / float(orig_w)
        new_w = max(120, int(orig_w * scale))
        new_h = max(120, int(orig_h * scale))
        im_small = im.resize((new_w, new_h))

    try:
        import numpy as np

        arr = np.array(im_small, dtype=np.uint8)
        white = float(np.percentile(arr, 90))
        thresh = int(max(80, min(230, white - 40)))
        ink = arr < thresh
        col_density = (ink.sum(axis=0) / max(1, ink.shape[0])).astype(float).tolist()
        debug.update({"threshold": thresh, "white_p90": white, "engine": "numpy"})
    except Exception:
        px = list(im_small.getdata())
        sample = px[:: max(1, len(px) // 20000)]
        sample_sorted = sorted(sample)
        white = float(sample_sorted[int(len(sample_sorted) * 0.90)]) if sample_sorted else 255.0
        thresh = int(max(80, min(230, white - 40)))
        w, h = im_small.size
        counts = [0] * w
        for i, v in enumerate(px):
            if v < thresh:
                counts[i % w] += 1
        col_density = [c / float(h) for c in counts]
        debug.update({"threshold": thresh, "white_p90": white, "engine": "python"})

    col_density = _smooth(col_density, window=11)
    w = len(col_density)

    mean_ink = sum(col_density) / max(1, len(col_density))
    ink_threshold = max(min_ink_ratio, mean_ink * 0.6)
    min_band_width = max(2, int(w * min_band_width_ratio))

    bands = _find_bands(col_density, threshold=ink_threshold, min_width=min_band_width)
    debug.update(
        {
            "mean_ink": mean_ink,
            "ink_threshold": ink_threshold,
            "bands_small": bands,
            "w_small": w,
        }
    )

    if len(bands) < min_columns:
        return VerticalDetectResult(False, [], {**debug, "reason": "insufficient bands"})

    widths = [b[1] - b[0] + 1 for b in bands]
    avg_width = sum(widths) / max(1, len(widths))
    if avg_width > (w * max_band_width_ratio):
        return VerticalDetectResult(False, [], {**debug, "reason": "bands too wide"})

    # Map bands back to original coordinates.
    columns: list[tuple[int, int]] = []
    for start, end in bands:
        x1 = int(round((start / max(1, w)) * orig_w))
        x2 = int(round(((end + 1) / max(1, w)) * orig_w))
        if x2 <= x1:
            continue
        if body_bbox is not None:
            bx1, _, _, _ = body_bbox
            x1 += bx1
            x2 += bx1
        columns.append((x1, x2))

    if not columns:
        return VerticalDetectResult(False, [], {**debug, "reason": "no columns"})

    return VerticalDetectResult(True, columns, debug)
