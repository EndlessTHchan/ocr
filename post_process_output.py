"""Post-process output.txt with DeepSeek to remove references and metadata.

Keeps main content; only removes references/copyright/publishing metadata.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ocr_tool.proofreading.deepseek import DeepSeekError, deepseek_chat_json, load_deepseek_config_from_env
from dotenv import load_dotenv

try:
    import transformers
except Exception:  # pragma: no cover
    transformers = None


def _extract_first_json_object(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return s
    if s.startswith("```"):
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1 :]
        end_fence = s.rfind("```")
        if end_fence != -1:
            s = s[:end_fence]
        s = s.strip()
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1].strip()
    return s


def _split_pages(text: str) -> list[str]:
    pattern = re.compile(r"(【原书第\s*\d+\s*页】\n)")
    parts = pattern.split(text)
    pages: list[str] = []
    i = 0
    while i < len(parts):
        if pattern.match(parts[i]):
            marker = parts[i]
            body = parts[i + 1] if i + 1 < len(parts) else ""
            pages.append(marker + body)
            i += 2
        else:
            if parts[i].strip():
                pages.append(parts[i])
            i += 1
    return pages


def _build_prompt(batch_text: str) -> tuple[str, str]:
    system = (
        "你是文本后处理编辑。目标：保留主要阅读内容，仅删除无关内容，并优化段落结构。\n"
        "删除范围（必须删除）：\n"
        "- 参考文献/References/Bibliography 列表\n"
        "- 版权页、出版/印刷/发行/合同登记/ISBN/CIP/责任编辑/出版人/社址/邮编/电话/网址/定价/版次/印次/开本/印张/字数等信息\n"
        "- 免责声明、版权声明、授权/出版协议类说明\n\n"
        "保留范围（必须保留）：\n"
        "- 正文、前言/序、目录、章节标题、正文段落\n\n"
        "规则：\n"
        "- 不得改写内容，不得总结，不得增删正文意思\n"
        "- 仅优化段落结构：合并被错误换行的句子，保持可读性\n"
        "- 如不确定是否为无关内容，宁可保留\n\n"
        "输出要求：只输出严格 JSON 对象，格式为 {\"text\": \"...\"}，不要Markdown。"
    )
    user = json.dumps({"text": batch_text}, ensure_ascii=False)
    return system, user


def _process_batch(text: str) -> str:
    cfg = load_deepseek_config_from_env()
    system, user = _build_prompt(text)
    raw = deepseek_chat_json(
        cfg,
        system=system,
        user=user,
        temperature=0.0,
        max_tokens=_process_batch.max_tokens,
    )
    try:
        obj = json.loads(_extract_first_json_object(raw))
    except Exception as e:
        raise DeepSeekError(f"Post-process output not valid JSON: {raw[:800]}") from e
    cleaned = obj.get("text")
    if not isinstance(cleaned, str):
        raise DeepSeekError("Post-process JSON missing 'text'")
    return cleaned


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-process output.txt with DeepSeek.")
    parser.add_argument("--input", default="out/output.txt", help="Input text path")
    parser.add_argument("--output", default="out/output.cleaned.txt", help="Output text path")
    parser.add_argument("--pages-per-batch", type=int, default=8, help="Pages per batch")
    parser.add_argument("--max-chars", type=int, default=4000, help="Max chars per batch")
    parser.add_argument(
        "--max-input-tokens",
        type=int,
        default=3500,
        help="Max input tokens per batch (requires tokenizer)",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=3072,
        help="Max output tokens per batch",
    )
    parser.add_argument(
        "--tokenizer-dir",
        default="token",
        help="Tokenizer directory for token counting",
    )
    args = parser.parse_args()

    load_dotenv()

    tokenizer = None
    if transformers is not None:
        try:
            tokenizer = transformers.AutoTokenizer.from_pretrained(
                args.tokenizer_dir,
                trust_remote_code=True,
            )
        except Exception:
            tokenizer = None

    in_path = Path(args.input)
    if not in_path.exists():
        raise SystemExit(f"Missing input: {in_path}")

    text = in_path.read_text(encoding="utf-8")
    pages = _split_pages(text)

    batches: list[str] = []
    current: list[str] = []
    current_len = 0
    current_tokens = 0
    for page in pages:
        page_tokens = len(tokenizer.encode(page)) if tokenizer is not None else 0
        would_exceed_tokens = (
            tokenizer is not None
            and current
            and (current_tokens + page_tokens) > max(500, int(args.max_input_tokens))
        )
        would_exceed_chars = current and (current_len + len(page)) > max(1000, int(args.max_chars))
        would_exceed_pages = current and len(current) >= max(1, int(args.pages_per_batch))

        if would_exceed_tokens or would_exceed_chars or would_exceed_pages:
            batches.append("".join(current))
            current = []
            current_len = 0
            current_tokens = 0

        current.append(page)
        current_len += len(page)
        if tokenizer is not None:
            current_tokens += page_tokens

    if current:
        batches.append("".join(current))

    _process_batch.max_tokens = int(args.max_output_tokens)
    out_chunks: list[str] = []
    for idx, batch in enumerate(batches, start=1):
        print(f"Processing batch {idx}/{len(batches)}...")
        out_chunks.append(_process_batch(batch))

    out_path = Path(args.output)
    out_path.write_text("\n".join(out_chunks), encoding="utf-8")
    print(f"Saved cleaned text to {out_path}")


if __name__ == "__main__":
    main()
