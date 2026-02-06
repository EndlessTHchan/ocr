from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-reasoner"
    timeout_s: int = 120


class DeepSeekError(RuntimeError):
    pass


def _extract_first_json_object(text: str) -> str:
    """Extract the first JSON object substring from a possibly wrapped response.

    DeepSeek (or network middleboxes) may return fenced blocks like ```json ... ```.
    We still enforce "JSON object only" at the prompt level, but this makes parsing resilient.
    """

    s = (text or "").strip()
    if not s:
        return s

    # Strip common fenced code block markers.
    if s.startswith("```"):
        # Remove leading fence line.
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1 :]
        # Remove trailing fence if present.
        end_fence = s.rfind("```")
        if end_fence != -1:
            s = s[:end_fence]
        s = s.strip()

    # Find the first JSON object.
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1].strip()
    return s


def load_deepseek_config_from_env() -> DeepSeekConfig:
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_KEY")
    if not api_key:
        raise DeepSeekError("Missing DEEPSEEK_API_KEY in environment/.env")

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    # Default to the reasoning model; can be overridden via DEEPSEEK_MODEL.
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner")
    timeout_s = int(os.getenv("DEEPSEEK_TIMEOUT_S", "120"))
    return DeepSeekConfig(api_key=api_key, base_url=base_url, model=model, timeout_s=timeout_s)


def _post_json(url: str, payload: dict[str, Any], *, api_key: str, timeout_s: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    max_retries = int(os.getenv("DEEPSEEK_MAX_RETRIES", "2"))
    backoff_s = float(os.getenv("DEEPSEEK_RETRY_BACKOFF_S", "1.0"))

    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw = resp.read().decode("utf-8")
            last_err = None
            break
        except urllib.error.HTTPError as e:
            # Retry only on rate limits / transient server errors.
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = ""
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(backoff_s * (2**attempt))
                last_err = e
                continue
            raise DeepSeekError(f"HTTP {e.code} from DeepSeek: {body[:800]}") from e
        except Exception as e:
            # Common transient errors on Windows: ConnectionResetError (WinError 10054)
            # and urllib.error.URLError.
            last_err = e
            if attempt < max_retries:
                time.sleep(backoff_s * (2**attempt))
                continue
            raise DeepSeekError(f"DeepSeek request failed: {e}") from e

    if last_err is not None:
        raise DeepSeekError(f"DeepSeek request failed: {last_err}") from last_err

    try:
        return json.loads(raw)
    except Exception as e:
        raise DeepSeekError(f"DeepSeek response not JSON: {raw[:800]}") from e


def deepseek_chat_json(
    cfg: DeepSeekConfig,
    *,
    system: str,
    user: str,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> str:
    """Calls an OpenAI-compatible chat completions endpoint and returns the assistant content."""

    url = f"{cfg.base_url}/v1/chat/completions"
    payload = {
        "model": cfg.model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Ask the OpenAI-compatible endpoint to enforce a JSON object response.
        # This is especially important for reasoning models that may otherwise emit explanations.
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    data = _post_json(url, payload, api_key=cfg.api_key, timeout_s=cfg.timeout_s)
    try:
        msg = data["choices"][0]["message"]
        content = (msg.get("content") or "")
        if not content.strip():
            # Some reasoning-model responses may place the usable text in `reasoning_content`.
            content = (msg.get("reasoning_content") or "")
        if not content.strip():
            raise KeyError("Empty message content")
        return content
    except Exception as e:
        raise DeepSeekError(f"Unexpected DeepSeek response shape: {str(data)[:800]}") from e


@dataclass(frozen=True)
class ProofreadChange:
    from_text: str
    to_text: str
    reason: str


@dataclass(frozen=True)
class ProofreadBlockResult:
    block_id: str
    corrected_text: str
    changes: list[ProofreadChange]
    role_suggestion: str = "body"
    keep_recommendation: str = "keep"
    keep_reason: str = ""


@dataclass(frozen=True)
class StructureHint:
    block_id: str
    kind: str  # e.g. "title" | "heading"
    level: int  # 1..6
    text: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class ProofreadResult:
    blocks: list[ProofreadBlockResult]
    structure_hints: list[StructureHint]
    meta: dict[str, Any]


@dataclass(frozen=True)
class ProofreadBlockResultPaged:
    page_id: int
    block_id: str
    corrected_text: str
    changes: list[ProofreadChange]
    role_suggestion: str = "body"
    keep_recommendation: str = "keep"
    keep_reason: str = ""


@dataclass(frozen=True)
class StructureHintPaged:
    page_id: int
    block_id: str
    kind: str
    level: int
    text: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class ProofreadPagesResult:
    blocks: list[ProofreadBlockResultPaged]
    structure_hints: list[StructureHintPaged]
    meta: dict[str, Any]


def build_proofread_prompt(
    *,
    page_id: int,
    blocks: list[dict[str, str]],
    domain_hint: str = "",
    glossary: Optional[list[str]] = None,
) -> tuple[str, str]:
    """Return (system, user) prompt that forces strict JSON output."""

    glossary = glossary or []
    system = (
        "你是 OCR 校对专家，为盲人用户优化扫描文档识别结果。\n"
        "核心任务：\n"
        "1) 最小化纠错：形近字/标点/术语/数字单位（禁止改写）\n"
        "2) 标注内容角色（role_suggestion），给出过滤建议（keep_recommendation，仅建议不删除）\n"
        "3) 提取章节结构（structure_hints，不虚构）\n\n"
        "说明：阅读顺序/分栏/竖排等排版处理已由上游程序完成，你不得重新排序、不得重组段落。\n\n"
        "修改规则：\n"
        "- 可以改：形近字（如 己/已、目/日）、专业术语（结合 domain_hint 与 glossary）、标点错误（引号不配对、中英混用、省略号格式）、OCR 噪点（多余空格、中文句号误用等）\n"
        "- 不能改：不得改写表达/改变风格；不得扩写/总结；不得合并/拆分段落；不得改变 block 顺序\n"
        "- 繁体书保持繁体，古籍引文保持原样\n\n"
        "角色标注（role_suggestion）：body|title|table|header|footer|caption|figure|page_number|footnote|other\n"
        "保留建议（keep_recommendation）：keep|drop|user_choice\n"
        "- keep：正文/标题/表格/脚注\n"
        "- drop：caption/figure/page_number（盲人朗读严重干扰，必须标注为 drop）\n"
        "- user_choice：header/footer（可能含章节信息，通常交给用户选择）\n\n"
        "特殊处理提示（仅用于校对/标注，不得重排）：\n"
        "- 表格：尽量保留文本，可用制表符分隔（如无法确定则保持原样）\n"
        "- 公式：保留符号，无法识别可在 keep_reason 或 meta.notes 里提示 [公式无法识别]\n\n"
        "输出要求：\n"
        "- 只输出严格 JSON（对象），不要 Markdown，不要代码块，不要任何解释文字\n"
        "- structure_hints 的 text 必须来自你输出的 corrected_text，不得虚构\n"
        "- 可在 meta.notes 中附带 layout_analysis（single_column/double_column/vertical_rtl/mixed）与质量问题提醒，但不得据此改动顺序\n"
    )

    user_obj = {
        "task": "proofread",
        "page_id": page_id,
        "domain_hint": domain_hint,
        "glossary": glossary,
        "blocks": blocks,
        "output_schema": {
            "blocks": [
                {
                    "block_id": "string (must match input)",
                    "corrected_text": "string (same meaning, minimal edits)",
                    "changes": [
                        {"from": "string", "to": "string", "reason": "string"}
                    ],
                    "role_suggestion": "header|footer|body|title|table|caption|figure|page_number|footnote|other",
                    "keep_recommendation": "keep|drop|user_choice",
                    "keep_reason": "string",
                }
            ],
            "structure_hints": [
                {
                    "block_id": "string (must match input)",
                    "kind": "title|heading",
                    "level": "integer 1-6 (1=chapter/title, 2=section, 3=subsection...)",
                    "text": "string (copied from corrected_text, no invention)",
                    "confidence": "number 0..1",
                    "reason": "string (why it's likely a title)",
                }
            ],
            "meta": {"notes": "string"},
        },
    }

    user = (
        "请对下列OCR文本做校对，严格按 output_schema 输出 JSON。\n"
        "再次强调：只输出JSON（对象），不要Markdown，不要代码块。\n\n"
        + json.dumps(user_obj, ensure_ascii=False)
    )

    return system, user


def build_proofread_prompt_pages(
    *,
    pages: list[dict[str, Any]],
    domain_hint: str = "",
    glossary: Optional[list[str]] = None,
) -> tuple[str, str]:
    """Return (system, user) prompt that forces strict JSON output for multiple pages."""

    glossary = glossary or []
    system = (
        "你是 OCR 校对专家，为盲人用户优化扫描文档识别结果。\n"
        "核心任务：\n"
        "1) 最小化纠错：形近字/标点/术语/数字单位（禁止改写）\n"
        "2) 标注内容角色（role_suggestion），给出过滤建议（keep_recommendation，仅建议不删除）\n"
        "3) 提取章节结构（structure_hints，不虚构）\n\n"
        "说明：本请求包含多页（pages）。阅读顺序/分栏/竖排等排版处理已由上游程序完成，你不得重新排序、不得重组段落。\n\n"
        "修改规则：\n"
        "- 可以改：形近字、专业术语（结合 domain_hint 与 glossary）、标点错误、OCR 噪点（多余空格等）\n"
        "- 不能改：不得改写表达/改变风格；不得扩写/总结；不得合并/拆分段落；不得改变 block 顺序\n"
        "- 繁体书保持繁体\n\n"
        "角色标注（role_suggestion）：body|title|table|header|footer|caption|figure|page_number|footnote|other\n"
        "保留建议（keep_recommendation）：keep|drop|user_choice\n"
        "- keep：正文/标题/表格/脚注\n"
        "- drop：caption/figure/page_number（必须 drop）\n"
        "- user_choice：header/footer（通常 user_choice）\n\n"
        "输出要求：\n"
        "- 只输出严格 JSON（对象），不要 Markdown，不要代码块，不要任何解释文字\n"
        "- structure_hints 的 text 必须来自 corrected_text，不得虚构\n"
        "- 可在 meta.notes 中附带 layout_analysis 与质量问题提醒（不影响顺序）\n"
    )

    user_obj = {
        "task": "proofread_pages",
        "domain_hint": domain_hint,
        "glossary": glossary,
        "pages": pages,
        "output_schema": {
            "blocks": [
                {
                    "page_id": "integer (must match input)",
                    "block_id": "string (must match input)",
                    "corrected_text": "string (same meaning, minimal edits)",
                    "changes": [
                        {"from": "string", "to": "string", "reason": "string"}
                    ],
                    "role_suggestion": "header|footer|body|title|table|caption|figure|page_number|footnote|other",
                    "keep_recommendation": "keep|drop|user_choice",
                    "keep_reason": "string",
                }
            ],
            "structure_hints": [
                {
                    "page_id": "integer (must match input)",
                    "block_id": "string (must match input)",
                    "kind": "title|heading",
                    "level": "integer 1-6 (1=chapter/title, 2=section, 3=subsection...)",
                    "text": "string (copied from corrected_text, no invention)",
                    "confidence": "number 0..1",
                    "reason": "string (why it's likely a title)",
                }
            ],
            "meta": {"notes": "string"},
        },
    }

    user = (
        "请对下列OCR文本做校对，严格按 output_schema 输出 JSON。\n"
        "再次强调：只输出JSON（对象），不要Markdown，不要代码块。\n\n"
        + json.dumps(user_obj, ensure_ascii=False)
    )
    return system, user


def parse_proofread_result(text: str) -> ProofreadResult:
    """Parse strict JSON response into dataclasses."""

    try:
        obj = json.loads(_extract_first_json_object(text))
    except Exception as e:
        raise DeepSeekError(f"Proofread output not valid JSON: {text[:800]}") from e

    blocks_raw = obj.get("blocks")
    if not isinstance(blocks_raw, list):
        raise DeepSeekError("Proofread JSON missing 'blocks' list")

    blocks: list[ProofreadBlockResult] = []
    allowed_roles = {
        "header",
        "footer",
        "body",
        "title",
        "table",
        "caption",
        "figure",
        "page_number",
        "footnote",
        "other",
    }
    allowed_keep = {"keep", "drop", "user_choice"}
    for b in blocks_raw:
        if not isinstance(b, dict):
            continue
        block_id = str(b.get("block_id", ""))
        corrected_text = str(b.get("corrected_text", ""))
        changes_list = b.get("changes") if isinstance(b.get("changes"), list) else []
        changes: list[ProofreadChange] = []
        for c in changes_list:
            if not isinstance(c, dict):
                continue
            changes.append(
                ProofreadChange(
                    from_text=str(c.get("from", "")),
                    to_text=str(c.get("to", "")),
                    reason=str(c.get("reason", "")),
                )
            )

        role = str(b.get("role_suggestion", "body")).strip() or "body"
        keep = str(b.get("keep_recommendation", "keep")).strip() or "keep"
        keep_reason = str(b.get("keep_reason", "")).strip()
        if role not in allowed_roles:
            role = "other"
        if keep not in allowed_keep:
            keep = "keep"

        blocks.append(
            ProofreadBlockResult(
                block_id=block_id,
                corrected_text=corrected_text,
                changes=changes,
                role_suggestion=role,
                keep_recommendation=keep,
                keep_reason=keep_reason,
            )
        )

    hints_raw = obj.get("structure_hints")
    hints: list[StructureHint] = []
    if isinstance(hints_raw, list):
        for h in hints_raw:
            if not isinstance(h, dict):
                continue
            block_id = str(h.get("block_id", ""))
            kind = str(h.get("kind", "heading"))
            try:
                level = int(h.get("level", 2))
            except Exception:
                level = 2
            level = max(1, min(6, level))
            text_v = str(h.get("text", "")).strip()
            try:
                confidence = float(h.get("confidence", 0.5))
            except Exception:
                confidence = 0.5
            confidence = max(0.0, min(1.0, confidence))
            reason = str(h.get("reason", "")).strip()
            if not block_id or not text_v:
                continue
            hints.append(
                StructureHint(
                    block_id=block_id,
                    kind=kind,
                    level=level,
                    text=text_v,
                    confidence=confidence,
                    reason=reason,
                )
            )

    meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
    return ProofreadResult(blocks=blocks, structure_hints=hints, meta=meta)


def parse_proofread_pages_result(text: str) -> ProofreadPagesResult:
    try:
        obj = json.loads(_extract_first_json_object(text))
    except Exception as e:
        raise DeepSeekError(f"Proofread output not valid JSON: {text[:800]}") from e

    blocks_raw = obj.get("blocks")
    if not isinstance(blocks_raw, list):
        raise DeepSeekError("Proofread JSON missing 'blocks' list")

    blocks: list[ProofreadBlockResultPaged] = []
    allowed_roles = {
        "header",
        "footer",
        "body",
        "title",
        "table",
        "caption",
        "figure",
        "page_number",
        "footnote",
        "other",
    }
    allowed_keep = {"keep", "drop", "user_choice"}
    for b in blocks_raw:
        if not isinstance(b, dict):
            continue
        try:
            page_id = int(b.get("page_id"))
        except Exception:
            continue
        block_id = str(b.get("block_id", ""))
        corrected_text = str(b.get("corrected_text", ""))
        changes_list = b.get("changes") if isinstance(b.get("changes"), list) else []
        changes: list[ProofreadChange] = []
        for c in changes_list:
            if not isinstance(c, dict):
                continue
            changes.append(
                ProofreadChange(
                    from_text=str(c.get("from", "")),
                    to_text=str(c.get("to", "")),
                    reason=str(c.get("reason", "")),
                )
            )
        if not block_id:
            continue

        role = str(b.get("role_suggestion", "body")).strip() or "body"
        keep = str(b.get("keep_recommendation", "keep")).strip() or "keep"
        keep_reason = str(b.get("keep_reason", "")).strip()
        if role not in allowed_roles:
            role = "other"
        if keep not in allowed_keep:
            keep = "keep"
        blocks.append(
            ProofreadBlockResultPaged(
                page_id=page_id,
                block_id=block_id,
                corrected_text=corrected_text,
                changes=changes,
                role_suggestion=role,
                keep_recommendation=keep,
                keep_reason=keep_reason,
            )
        )

    hints_raw = obj.get("structure_hints")
    hints: list[StructureHintPaged] = []
    if isinstance(hints_raw, list):
        for h in hints_raw:
            if not isinstance(h, dict):
                continue
            try:
                page_id = int(h.get("page_id"))
            except Exception:
                continue
            block_id = str(h.get("block_id", ""))
            kind = str(h.get("kind", "heading"))
            try:
                level = int(h.get("level", 2))
            except Exception:
                level = 2
            level = max(1, min(6, level))
            text_v = str(h.get("text", "")).strip()
            try:
                confidence = float(h.get("confidence", 0.5))
            except Exception:
                confidence = 0.5
            confidence = max(0.0, min(1.0, confidence))
            reason = str(h.get("reason", "")).strip()
            if not block_id or not text_v:
                continue
            hints.append(
                StructureHintPaged(
                    page_id=page_id,
                    block_id=block_id,
                    kind=kind,
                    level=level,
                    text=text_v,
                    confidence=confidence,
                    reason=reason,
                )
            )

    meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
    return ProofreadPagesResult(blocks=blocks, structure_hints=hints, meta=meta)


def safe_similarity(a: str, b: str) -> float:
    # Cheap similarity check to prevent large rewrites.
    import difflib

    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def deepseek_proofread_blocks(
    *,
    cfg: DeepSeekConfig,
    page_id: int,
    blocks: list[dict[str, str]],
    domain_hint: str = "",
    glossary: Optional[list[str]] = None,
    min_similarity: float = 0.90,
    max_len_ratio: float = 1.10,
) -> ProofreadResult:
    system, user = build_proofread_prompt(
        page_id=page_id, blocks=blocks, domain_hint=domain_hint, glossary=glossary
    )

    # 1st attempt
    raw = deepseek_chat_json(cfg, system=system, user=user, temperature=0.0, max_tokens=2048)
    try:
        parsed = parse_proofread_result(raw)
    except DeepSeekError:
        # 2nd attempt: ask to fix JSON only
        repair_user = (
            "你上一次输出的内容不是严格JSON。请只输出严格JSON对象，符合 output_schema。\n"
            "不要任何解释，不要Markdown，不要代码块。\n\n"
            f"原输出如下：\n{raw[:2000]}"
        )
        raw2 = deepseek_chat_json(cfg, system=system, user=repair_user, temperature=0.0, max_tokens=2048)
        parsed = parse_proofread_result(raw2)

    # Guardrails
    by_id_in = {b["block_id"]: b.get("text", "") for b in blocks}
    safe_blocks: list[ProofreadBlockResult] = []
    for out_b in parsed.blocks:
        original = by_id_in.get(out_b.block_id)
        if original is None:
            continue
        corrected = out_b.corrected_text

        if not corrected:
            safe_blocks.append(out_b)
            continue

        if len(original) > 0:
            ratio = len(corrected) / len(original)
            if ratio > max_len_ratio or ratio < (1.0 / max_len_ratio):
                # Reject risky rewrite
                safe_blocks.append(
                    ProofreadBlockResult(
                        block_id=out_b.block_id,
                        corrected_text=original,
                        changes=[],
                        role_suggestion=out_b.role_suggestion,
                        keep_recommendation=out_b.keep_recommendation,
                        keep_reason=out_b.keep_reason,
                    )
                )
                continue

        sim = safe_similarity(original, corrected)
        if sim < min_similarity:
            safe_blocks.append(
                ProofreadBlockResult(
                    block_id=out_b.block_id,
                    corrected_text=original,
                    changes=[],
                    role_suggestion=out_b.role_suggestion,
                    keep_recommendation=out_b.keep_recommendation,
                    keep_reason=out_b.keep_reason,
                )
            )
            continue

        safe_blocks.append(out_b)

    # Validate structure hints: must reference existing blocks, and should be reasonably short.
    safe_hints: list[StructureHint] = []
    for h in parsed.structure_hints:
        original = by_id_in.get(h.block_id)
        if original is None:
            continue
        if len(h.text) > 200:
            continue
        safe_hints.append(h)

    meta = dict(parsed.meta)
    meta.update({"min_similarity": min_similarity, "max_len_ratio": max_len_ratio, "ts": int(time.time())})
    return ProofreadResult(blocks=safe_blocks, structure_hints=safe_hints, meta=meta)


def deepseek_proofread_pages(
    *,
    cfg: DeepSeekConfig,
    pages: list[dict[str, Any]],
    domain_hint: str = "",
    glossary: Optional[list[str]] = None,
    min_similarity: float = 0.90,
    max_len_ratio: float = 1.10,
) -> ProofreadPagesResult:
    system, user = build_proofread_prompt_pages(pages=pages, domain_hint=domain_hint, glossary=glossary)

    raw = deepseek_chat_json(cfg, system=system, user=user, temperature=0.0, max_tokens=4096)
    try:
        parsed = parse_proofread_pages_result(raw)
    except DeepSeekError:
        repair_user = (
            "你上一次输出的内容不是严格JSON。请只输出严格JSON对象，符合 output_schema。\n"
            "不要任何解释，不要Markdown，不要代码块。\n\n"
            f"原输出如下：\n{raw[:2000]}"
        )
        raw2 = deepseek_chat_json(cfg, system=system, user=repair_user, temperature=0.0, max_tokens=4096)
        parsed = parse_proofread_pages_result(raw2)

    # Build input lookup by (page_id, block_id)
    by_key_in: dict[tuple[int, str], str] = {}
    for p in pages:
        try:
            pid = int(p.get("page_id"))
        except Exception:
            continue
        blocks_in = p.get("blocks")
        if not isinstance(blocks_in, list):
            continue
        for b in blocks_in:
            if not isinstance(b, dict):
                continue
            bid = str(b.get("block_id", ""))
            txt = str(b.get("text", ""))
            if not bid:
                continue
            by_key_in[(pid, bid)] = txt

    safe_blocks: list[ProofreadBlockResultPaged] = []
    for out_b in parsed.blocks:
        original = by_key_in.get((out_b.page_id, out_b.block_id))
        if original is None:
            continue
        corrected = out_b.corrected_text

        if not corrected:
            safe_blocks.append(out_b)
            continue

        if len(original) > 0:
            ratio = len(corrected) / len(original)
            if ratio > max_len_ratio or ratio < (1.0 / max_len_ratio):
                safe_blocks.append(
                    ProofreadBlockResultPaged(
                        page_id=out_b.page_id,
                        block_id=out_b.block_id,
                        corrected_text=original,
                        changes=[],
                        role_suggestion=out_b.role_suggestion,
                        keep_recommendation=out_b.keep_recommendation,
                        keep_reason=out_b.keep_reason,
                    )
                )
                continue

        sim = safe_similarity(original, corrected)
        if sim < min_similarity:
            safe_blocks.append(
                ProofreadBlockResultPaged(
                    page_id=out_b.page_id,
                    block_id=out_b.block_id,
                    corrected_text=original,
                    changes=[],
                    role_suggestion=out_b.role_suggestion,
                    keep_recommendation=out_b.keep_recommendation,
                    keep_reason=out_b.keep_reason,
                )
            )
            continue

        safe_blocks.append(out_b)

    safe_hints: list[StructureHintPaged] = []
    for h in parsed.structure_hints:
        original = by_key_in.get((h.page_id, h.block_id))
        if original is None:
            continue
        if len(h.text) > 200:
            continue
        safe_hints.append(h)

    meta = dict(parsed.meta)
    meta.update({"min_similarity": min_similarity, "max_len_ratio": max_len_ratio, "ts": int(time.time())})
    return ProofreadPagesResult(blocks=safe_blocks, structure_hints=safe_hints, meta=meta)
