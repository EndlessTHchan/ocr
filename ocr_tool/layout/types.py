from __future__ import annotations

from pydantic import BaseModel

from ..models import Block


class LayoutResult(BaseModel):
    blocks: list[Block]
