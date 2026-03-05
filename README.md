# ocr-tool · 扫描 PDF → 可读 TXT

一个面向无障碍场景的扫描 PDF 转 TXT 工具。支持：

- 将扫描版 PDF 渲染为高 DPI 图片
- 版面分析（页眉/正文/页脚）、双栏检测、竖排（右到左）检测
- 调用 AIStudio 布局解析 / OCR API 获取文本
- 集成 DeepSeek 对 OCR 结果做“最小化纠错 + 结构标注”
- 输出适合读屏/无障碍阅读的纯文本，并保留必要的页信息与章节结构

本仓库同时提供：

- 命令行入口：`ocr_tool.cli`
- 一键脚本：`quick_run.py`
- Gradio Web UI：`app.py`

> 更偏「怎么用」的中文说明可参考：[PROJECT_GUIDE.md](PROJECT_GUIDE.md) 和 [快速使用.txt](快速使用.txt)。

---

## 1. 功能特性概览

- **无障碍优先（accessible-first）**：为盲人或低视力用户设计，默认过滤页码、版权页、图注等噪声，保留正文和结构信息。
- **版面分析与阅读顺序重建**
  - 基于启发式规则将页面划分为 header/body/footer。
  - 使用灰度投影与列密度统计，检测双栏排版与竖排（vertical right-to-left）排版。
  - 针对单栏 / 双栏 / 竖排分别采用不同的排序策略，重建阅读顺序。
- **AIStudio OCR 集成**
  - 通过 `AISTUDIO_TOKEN` 调用 AIStudio 布局解析 / OCR API。
  - 支持文档方向分类、扭曲矫正、图表识别等可配置开关。
- **DeepSeek 校对与结构标注**
  - 使用 DeepSeek Chat API，对 OCR 结果进行“最小改动”的字词级纠错。
  - 标注文本角色（标题/正文/页眉/脚注/图注等），提取章节结构信息。
- **可调批处理与调试友好**
  - 支持按页批处理，控制每批最大页数/字符数/块数，兼顾吞吐与稳定性。
  - 每页生成 JSON 调试文件，包含版面、排序、OCR、校对、原始 AIStudio 返回等信息，方便排查问题。

---

## 2. 环境准备

- Python 版本：**3.10–3.11**（`pyproject.toml` 要求 `>=3.10,<3.12`）
- 操作系统：Windows（仓库中脚本以 Windows 为主，但核心代码跨平台）

### 2.1 克隆仓库

```bash
git clone git@github.com:EndlessTHchan/ocr.git
cd ocr
```

### 2.2 创建并激活虚拟环境（Windows PowerShell）

```powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
```

### 2.3 安装依赖

```bash
pip install -r requirements.txt
```

> 目前 OCR 依赖主要通过 **AIStudio 远程 API** 完成，不再强制依赖 PaddleOCR/VL 本地模型；如果你有本地 OCR 需求，请参考历史版本或自行扩展。

---

## 3. 配置密钥（.env）

项目根目录下新建 `.env` 文件（或通过 Gradio UI / 交互式输入设置），常用变量：

```env
# DeepSeek（可选，用于 OCR 校对与后处理）
DEEPSEEK_API_KEY=你的DeepSeek API Key
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# AIStudio OCR（必选，用于实际 OCR）
AISTUDIO_TOKEN=你的AIStudio token
# 可选，默认由代码内置
AISTUDIO_API_URL=https://your-aistudio-endpoint/layout-parsing
```

说明：

- `quick_run.py` 会在 Key 缺失时，**交互式提示输入**，并写入当前进程环境变量。
- `app.py`（Gradio UI）提供了「API Key 设置」页，可直接保存到 `.env` 文件。

更多 DeepSeek 细节可参考：[ocr_tool/proofreading/deepseek.py](ocr_tool/proofreading/deepseek.py)。

---

## 4. 快速开始

### 4.1 一键脚本：`quick_run.py`

这是最推荐的入口，会自动执行：

1. AIStudio OCR + 排版 + 阅读顺序重建
2. DeepSeek 校对（可选）
3. DeepSeek 后处理清理参考文献/版权信息等（可选）

```bash
python quick_run.py input.pdf --mode aistudio+deepseek
```

常用参数：

- `--mode`
  - `aistudio+deepseek`：AIStudio OCR + DeepSeek 校对 + （可选）后处理
  - `aistudio+none`：仅 AIStudio OCR
  - `none`：只做拆页/排版/导出，不调用任何 OCR
- `--config`：配置文件路径（默认 `run_config.json`），可用来覆盖 `DEFAULT_CONFIG`
- `--outdir`：输出目录（默认 `out`）
- `--aistudio-token`：命令行直接传入 AIStudio Token，优先级高于 `.env`
- `--deepseek-key`：命令行直接传入 DeepSeek API Key
- `--aistudio-api-url`：自定义 AIStudio API URL
- `--no-post-process`：跳过后处理（只做 OCR + 校对）

输出示例：

- `out/output.txt`：主流程导出的 TXT
- `out/output.cleaned.txt`：DeepSeek 后处理清理后的 TXT（默认开启）

### 4.2 命令行：`ocr_tool.cli`

如需细粒度控制，可以直接调用 Typer CLI：

```bash
python -m ocr_tool.cli run input.pdf \
  --outdir out \
  --dpi 300 \
  --ocr-engine aistudio \
  --columns auto \
  --reading-direction auto \
  --proofread-engine deepseek
```

关键参数（节选，对应 [ocr_tool/cli.py](ocr_tool/cli.py)）：

- 输入输出与分页
  - `pdf`：输入扫描 PDF 路径
  - `--outdir`：输出目录（默认 `out`）
  - `--dpi`：渲染 DPI（72–600，默认 300）
  - `--page-batch-size`：按批处理页数（默认 20）
  - `--max-pages`：限制处理总页数（默认全量）
- 版面与阅读顺序
  - `--columns`：`auto|single|double`，自动/强制单栏/强制双栏
  - `--reading-direction`：`auto|horizontal|vertical_rtl`，自动/横排/竖排右到左
- 过滤与页眉页脚
  - `--keep-header` / `--keep-footer` / `--keep-caption`：是否保留页眉/页脚/图注
  - `--include-page-markers`：是否在输出中插入 `【原书第 N 页】` 标记（默认开启）
- AIStudio OCR
  - `--ocr-engine`：`none|aistudio`（默认 `aistudio`）
  - `--aistudio-api-url`：AIStudio OCR API URL（默认从 `.env` 或内置）
  - `--aistudio-token`：AIStudio OCR Token（默认从 `.env` 读取）
  - `--aistudio-use-doc-orientation-classify`：是否启用文档方向分类
  - `--aistudio-use-doc-unwarping`：是否启用文档扭曲矫正
  - `--aistudio-use-chart-recognition`：是否启用图表识别
  - `--aistudio-timeout-s`：AIStudio 请求超时（秒，默认 300）
- DeepSeek 校对
  - `--proofread-engine`：`none|deepseek`
  - `--proofread-domain-hint`：可选领域提示，例如 `考研政治`
  - `--proofread-glossary`：术语表文件（每行一个术语）
  - `--proofread-max-chars` / `--proofread-max-blocks` / `--proofread-pages`：控制单次请求的字符数、块数和页数上限

运行后，会在终端打印进度信息，并在 `out` 目录下生成调试和输出文件（见下文）。

### 4.3 Gradio Web UI：`app.py`

如果你更习惯图形界面，可以启动 Web UI：

```bash
python app.py
```

启动后，在浏览器中打开控制台打印的本地地址（通常是 `http://127.0.0.1:7860`）：

- **API Key 设置** 页签：填写并保存 DeepSeek / AIStudio 的 Key 到 `.env`。
- **开始 OCR** 页签：上传 PDF，选择模式（如 `aistudio+deepseek`），设置 DPI、列模式、最大页数等，实时查看日志输出。

界面会在处理完成后提示输出 TXT 文件路径（`output.txt` 或 `output.cleaned.txt`）。

---

## 5. 输出结构与调试文件

以默认 `out` 目录为例：

```text
out/
  pages/
    0001.png          # 第 1 页渲染图像
    0001.json         # 第 1 页的调试 JSON
    0002.png
    0002.json
    ...
  output.txt          # 主流程合成的 TXT
  output.cleaned.txt  # （可选）DeepSeek 后处理清理后的 TXT
```

其中：

- `pages/*.json` 中包含：
  - `blocks`：版面块列表，每个块包含 `block_id`、`type`（header/footer/text/figure/table/...）、`bbox`、`raw_text` 等。
  - `ordered_block_ids`：该页阅读顺序下的块 ID 列表。
  - `column_detect`：双栏/竖排检测的调试信息（如阈值、分割线位置等）。
  - `proofread`：DeepSeek 校对的结构化结果（按块的改动、角色建议、章节结构提示等）。
  - `aistudio_result`：AIStudio 原始返回结果（用于进一步脚本处理）。

TXT 输出：

- `output.txt`：按每页 `ordered_block_ids` 顺序，结合过滤策略，将文本块拼接成适合读屏的纯文本。
- `output.cleaned.txt`：再经过一次 DeepSeek 后处理（`post_process_output.py`），自动尝试删除参考文献、版权页、出版信息等冗余内容。

---

## 6. DeepSeek 后处理脚本

除了主流程中的校对，还提供单独的后处理脚本：[post_process_output.py](post_process_output.py)。

示例：

```bash
python post_process_output.py \
  --input out/output.txt \
  --output out/output.cleaned.txt \
  --pages-per-batch 8 \
  --max-chars 4000 \
  --max-input-tokens 3500 \
  --max-output-tokens 3072 \
  --tokenizer-dir token
```

脚本会：

- 按页批量切分输入文本，控制单次请求的最大字符数和 token 数，避免超长。
- 使用 DeepSeek 对文本做轻量清理，尽量删除：
  - 参考文献 / Bibliography / References
  - 版权页、出版信息（ISBN、印次、开本等）
  - 明显为图注/插图说明的内容

如果想单独估算 token 数量，可使用：[token/deepseek_tokenizer.py](token/deepseek_tokenizer.py)。

---

## 7. 适用场景与限制

适用场景：

- 扫描版图书、试卷、教材、讲义等 PDF。
- 以 **中文内容** 为主，DeepSeek 提示词也偏向中文无障碍场景。
- 需要获得结构化、阅读顺序正确、噪声较少的 TXT，用于读屏或后续 NLP 处理。

当前限制：

- 依赖 AIStudio 远程服务进行 OCR，网络状况会影响整体速度与稳定性。
- 对复杂混排（多栏 + 大量图表）文档，双栏/竖排检测可能不完美，需要根据 `pages/*.json` 手工检查。
- DeepSeek 只做“最小纠错 + 结构标注”，不会重排段落或改写内容，仍可能残留部分噪声或 OCR 错误。

---

## 8. 项目结构速览

- `ocr_tool/`
  - `cli.py`：Typer 命令行入口。
  - `pipeline.py`：主处理流水线（PDF 拆页 → 版面分析 → 列检测 → OCR → 校对 → 导出）。
  - `models.py`：Pydantic 数据模型（`RunConfig`、`PageResult`、`Block` 等）。
  - `layout/`：简单版面分析（页眉/正文/页脚划分）。
  - `ordering/`：双栏/竖排检测与阅读顺序算法。
  - `ocr/`：OCR 引擎封装与 AIStudio 集成。
  - `proofreading/`：DeepSeek 校对与后处理相关逻辑。
  - `export/`：TXT 等格式导出。
- `quick_run.py`：一键运行脚本。
- `app.py`：Gradio Web UI。
- `post_process_output.py`：基于 DeepSeek 的文本后处理脚本。
- `token/`：DeepSeek tokenizer 及配置（估算 token 数）。

---

## 9. 开发与贡献

欢迎在 GitHub 上提交 Issue 或 Pull Request：

- 仓库地址：<https://github.com/EndlessTHchan/ocr>

开发者建议：

- 修改核心逻辑后，建议使用一两个代表性的 PDF（单栏书籍 / 双栏论文 / 竖排书籍）全流程跑一遍，检查：
  - `pages/*.json` 中的 `ordered_block_ids` 是否符合预期阅读顺序；
  - `output.txt` / `output.cleaned.txt` 是否有明显错行或大量噪声。

如需在简历中描述本项目，可以突出：

- 「扫描 PDF → TXT 的无障碍 OCR 工具」
- 「AIStudio OCR + DeepSeek LLM 校对 + 阅读顺序重建 + 多栏/竖排检测」
