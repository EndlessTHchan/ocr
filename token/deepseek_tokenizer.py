"""Token counter and batch-size helper for DeepSeek.

Usage:
    python deepseek_tokenizer.py --input ../out/output.txt --tokenizer-dir .
"""
import argparse

import transformers


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute token counts and suggest batch size.")
    parser.add_argument("--input", default="test.txt", help="Input text file")
    parser.add_argument("--tokenizer-dir", default="./", help="Tokenizer directory")
    parser.add_argument("--max-input-tokens", type=int, default=3500, help="Target input tokens per batch")
    args = parser.parse_args()

    tokenizer = transformers.AutoTokenizer.from_pretrained(
        args.tokenizer_dir, trust_remote_code=True
    )

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()

    token_ids = tokenizer.encode(text)
    total_tokens = len(token_ids)
    total_chars = len(text)
    chars_per_token = (total_chars / total_tokens) if total_tokens else 0.0
    suggested_max_chars = int(args.max_input_tokens * chars_per_token)

    print(f"Total tokens: {total_tokens}")
    print(f"Total chars: {total_chars}")
    print(f"Chars per token: {chars_per_token:.2f}")
    print(f"Suggested max chars per batch: {suggested_max_chars}")


if __name__ == "__main__":
    main()
