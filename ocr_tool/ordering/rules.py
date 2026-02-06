from __future__ import annotations

from ..models import Block


def order_blocks_single_column(blocks: list[Block]) -> list[str]:
    # y1 asc, tie-breaker x1 asc
    return [b.block_id for b in sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))]


def order_blocks_double_column(blocks: list[Block], split_x: int) -> list[str]:
    left: list[Block] = []
    right: list[Block] = []

    for b in blocks:
        cx = (b.bbox[0] + b.bbox[2]) / 2
        (left if cx < split_x else right).append(b)

    left_ids = order_blocks_single_column(left)
    right_ids = order_blocks_single_column(right)
    return left_ids + right_ids


def order_blocks_double_column_with_header_footer(blocks: list[Block], split_x: int) -> list[str]:
    """Two-column order, but keep header/footer outside of column interleaving."""

    headers = [b for b in blocks if b.type.value == "header"]
    footers = [b for b in blocks if b.type.value == "footer"]
    body = [b for b in blocks if b not in headers and b not in footers]

    ordered: list[str] = []
    ordered += order_blocks_single_column(headers)
    ordered += order_blocks_double_column(body, split_x=split_x)
    ordered += order_blocks_single_column(footers)
    return ordered


def order_blocks_vertical_rtl(blocks: list[Block]) -> list[str]:
    # x1 desc (right to left), tie-breaker y1 asc
    return [b.block_id for b in sorted(blocks, key=lambda b: (-b.bbox[0], b.bbox[1]))]


def order_blocks_vertical_rtl_with_header_footer(blocks: list[Block]) -> list[str]:
    headers = [b for b in blocks if b.type.value == "header"]
    footers = [b for b in blocks if b.type.value == "footer"]
    body = [b for b in blocks if b not in headers and b not in footers]

    ordered: list[str] = []
    ordered += order_blocks_single_column(headers)
    ordered += order_blocks_vertical_rtl(body)
    ordered += order_blocks_single_column(footers)
    return ordered


def order_blocks_auto(blocks: list[Block], page_width: int) -> list[str]:
    """A conservative auto mode.

    For now, this defaults to single-column ordering.
    We will add a deterministic column detector later (projection valley + downgrade rules).
    """

    _ = page_width
    return order_blocks_single_column(blocks)
