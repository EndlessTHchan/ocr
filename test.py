"""Call the AIStudio PaddleOCR API to parse a local file and save outputs."""

import base64
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()

API_URL = "https://bbe186c9acy0c7aa.aistudio-app.com/layout-parsing"
TOKEN = os.getenv("AISTUDIO_TOKEN")
FILE_PATH = os.getenv("AISTUDIO_FILE", "0001.png")
OUTPUT_DIR = Path(os.getenv("AISTUDIO_OUTPUT", "output"))


def guess_file_type(path: Path) -> int:
	if path.suffix.lower() == ".pdf":
		return 0
	return 1


def main() -> None:
	if not TOKEN:
		raise SystemExit("Missing AISTUDIO_TOKEN in environment.")

	path = Path(FILE_PATH)
	if not path.exists():
		raise SystemExit(f"File not found: {path}")

	file_bytes = path.read_bytes()
	file_data = base64.b64encode(file_bytes).decode("ascii")

	headers = {
		"Authorization": f"token {TOKEN}",
		"Content-Type": "application/json",
	}

	payload = {
		"file": file_data,
		"fileType": guess_file_type(path),
		"useDocOrientationClassify": False,
		"useDocUnwarping": False,
		"useChartRecognition": False,
	}

	resp = requests.post(API_URL, json=payload, headers=headers, timeout=300)
	print(resp.status_code)
	resp.raise_for_status()

	result = resp.json().get("result", {})
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

	raw_json_path = OUTPUT_DIR / "result.json"
	raw_json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
	print(f"JSON saved at {raw_json_path}")

	for i, res in enumerate(result.get("layoutParsingResults", [])):
		md_filename = OUTPUT_DIR / f"doc_{i}.md"
		md_filename.write_text(res.get("markdown", {}).get("text", ""), encoding="utf-8")
		print(f"Markdown document saved at {md_filename}")

		for img_path, img_url in res.get("markdown", {}).get("images", {}).items():
			full_img_path = OUTPUT_DIR / img_path
			full_img_path.parent.mkdir(parents=True, exist_ok=True)
			img_bytes = requests.get(img_url, timeout=60).content
			full_img_path.write_bytes(img_bytes)
			print(f"Image saved to: {full_img_path}")

		for img_name, img_url in res.get("outputImages", {}).items():
			img_response = requests.get(img_url, timeout=60)
			if img_response.status_code == 200:
				filename = OUTPUT_DIR / f"{img_name}_{i}.jpg"
				filename.write_bytes(img_response.content)
				print(f"Image saved to: {filename}")
			else:
				print(f"Failed to download image, status code: {img_response.status_code}")


if __name__ == "__main__":
	main()