# OCR 工具使用说明

这份文档以“怎么用”为主，其他设计细节仅作必要补充。

## 1. 快速开始（推荐）

1) 安装基础依赖：
```
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

2) 安装 OCR 依赖（需要真实识别时）：
```
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-ocr.txt
```

3) 跑一遍 OCR（不启用大模型校对）：
```
.\.venv\Scripts\python.exe -m ocr_tool.cli run input.pdf --ocr-engine paddle --proofread-engine none
```

## 2. 常见用法

### 仅拆页 + 排版 + 输出（不做 OCR）
```
.\.venv\Scripts\python.exe -m ocr_tool.cli run input.pdf --ocr-engine none
```

### 只用 Paddle OCR（不启用 DeepSeek）
```
.\.venv\Scripts\python.exe -m ocr_tool.cli run input.pdf --ocr-engine paddle --proofread-engine none
```

### 启用 DeepSeek 轻量校对
```
.\.venv\Scripts\python.exe -m ocr_tool.cli run input.pdf --ocr-engine paddle --proofread-engine deepseek
```

### 去水印（预处理）
```
.\.venv\Scripts\python.exe -m ocr_tool.cli run input.pdf --ocr-engine paddle --watermark-filter
```

### 微调 OCR 参数（降低水印干扰示例）
```
.\.venv\Scripts\python.exe -m ocr_tool.cli run input.pdf --ocr-engine paddle \
	--det-db-thresh 0.4 --det-db-box-thresh 0.7 --det-db-unclip-ratio 1.8 \
	--rec-score-thresh 0.5
```

### 产线高级参数（JSON 传入 PaddleOCR）
```
{
	"use_doc_orientation_classify": true,
	"use_doc_unwarping": true,
	"use_textline_orientation": true,
	"det_db_thresh": 0.4,
	"det_db_box_thresh": 0.7,
	"det_db_unclip_ratio": 1.8,
	"rec_score_thresh": 0.5
}
```

```
.\.venv\Scripts\python.exe -m ocr_tool.cli run input.pdf --ocr-engine paddle \
	--paddle-ocr-config paddle_ocr_config.json
```

### 竖排（右到左）阅读顺序
```
.\.venv\Scripts\python.exe -m ocr_tool.cli run input.pdf --ocr-engine paddle --reading-direction vertical_rtl
```

### 使用 PaddleOCR-VL（本地模型）
```
.\.venv\Scripts\python.exe -m ocr_tool.cli run input.pdf --ocr-engine vl \
	--vl-model-dir models/PaddleOCR-VL-1.5 \
	--vl-pipeline-version v1.5
```

## 3. 关键参数（最常用）

- `--outdir`：输出目录，默认 `out`
- `--dpi`：渲染 DPI（默认 300）
- `--columns`：`auto|single|double`
- `--reading-direction`：`auto|horizontal|vertical_rtl`
- `--watermark-filter`：启用轻量去水印预处理
- `--use-doc-orientation-classify`：是否启用文档方向分类
- `--use-doc-unwarping`：是否启用文档矫正
- `--use-textline-orientation`：是否启用文本行方向分类
- `--det-db-thresh`：文本检测阈值（越高越严格）
- `--det-db-box-thresh`：文本检测框阈值（越高越严格）
- `--det-db-unclip-ratio`：检测框扩张系数（越大越容易合并）
- `--rec-score-thresh`：识别置信度阈值（越高越保守）
- `--paddle-ocr-config`：以 JSON 传入 PaddleOCR 初始化参数
- `--vl-model-dir`：PaddleOCR-VL 本地模型目录
- `--vl-pipeline-version`：PaddleOCR-VL 版本（v1 或 v1.5）
- `--vl-use-layout-detection`：PaddleOCR-VL 版面检测开关
- `--keep-header` / `--keep-footer` / `--keep-caption`
- `--include-page-markers`：是否插入 `【原书第 N 页】`
- `--language`：PaddleOCR 语言（默认 `ch`）
- `--proofread-max-chars` / `--proofread-max-blocks` / `--proofread-pages`：控制 DeepSeek 批量大小

## 4. 输出产物

每次运行都会生成：
- `out_dir/pages/0001.png`：页图
- `out_dir/pages/0001.json`：该页的调试数据（含排序、OCR、校对建议等）
- `out_dir/output.txt`：最终纯文本

## 5. DeepSeek 配置（可选）

在 [.env](.env) 中配置：

```
DEEPSEEK_API_KEY=你的Key
DEEPSEEK_MODEL=deepseek-reasoner
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_TIMEOUT_S=120
DEEPSEEK_MAX_RETRIES=2
DEEPSEEK_RETRY_BACKOFF_S=1.0
```

说明：DeepSeek 只负责“最小纠错 + 结构标注”，不会重排或删段。

## 6. Windows 环境注意事项（OCR）

OCR 依赖见 [requirements-ocr.txt](requirements-ocr.txt)。

当前环境下：
- PaddlePaddle 必须从官方源安装。
- 如果更换 PaddlePaddle 版本，请先完整跑一遍真实 PDF 验证稳定性。

PaddleOCR-VL 额外说明：
- 需要安装 `paddleocr[doc-parser]` 额外依赖。
- 模型下载后放到本地目录（例如 `models/PaddleOCR-VL-1.5`），通过 `--vl-model-dir` 指定。

## 7. 常见问题排查

- 识别结果为空：确认已安装 OCR 依赖，并检查 `--language`。
- 顺序不对：查看 `out_dir/pages/*.json` 中的 `ordered_block_ids`。
- DeepSeek 报错：检查 [.env](.env) 是否配置，Key 是否有效。
- 出现 `ConvertPirAttribute2RuntimeAttribute` 报错：通常是 PaddlePaddle 3.x 在 Windows/CPU 的运行时问题，优先更换 PaddlePaddle 3.x 的不同构建或版本并重新验证。

## 8. 代码入口（仅供定位）

- CLI 入口：[ocr_tool/cli.py](ocr_tool/cli.py)
- 流程主控：[ocr_tool/pipeline.py](ocr_tool/pipeline.py)
- OCR 封装：[ocr_tool/ocr/engine.py](ocr_tool/ocr/engine.py)
- DeepSeek 校对：[ocr_tool/proofreading/deepseek.py](ocr_tool/proofreading/deepseek.py)
