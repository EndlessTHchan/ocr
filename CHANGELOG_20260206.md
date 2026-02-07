# 变更记录 - 2026-02-06

时间：2026-02-06 19:08 +08:00

修改说明：
- 新增竖排（右到左）检测与排序能力，可与原有单/双栏并存。
- 新增 CLI 参数 `--reading-direction`，用于控制阅读方向。
- OCR 依赖改为 PaddleOCR 3.4，PaddlePaddle 版本范围更新为 3.x。
- 用法文档改为中文并补充新参数说明。

修改出处：
- ocr_tool/ordering/column_detect.py
- ocr_tool/ordering/rules.py
- ocr_tool/pipeline.py
- ocr_tool/models.py
- ocr_tool/cli.py
- requirements-ocr.txt
- PROJECT_GUIDE.md

---

时间：2026-02-06 19:20 +08:00

修改说明：
- 用法文档补充竖排（右到左）运行示例。
- 常见问题增加 PaddlePaddle 3.x 在 Windows/CPU 的运行时错误说明。

修改出处：
- PROJECT_GUIDE.md

---

时间：2026-02-06 19:35 +08:00

修改说明：
- 卸载 Paddle 相关依赖（paddleocr、paddlex）。

修改出处：
- 环境依赖（.venv）

---

时间：2026-02-06 19:42 +08:00

修改说明：
- 降级 PaddleOCR 到 3.3.0，并匹配安装 paddlex 3.3.x。

修改出处：
- 环境依赖（.venv）

---

时间：2026-02-06 19:58 +08:00

修改说明：
- 兼容 PaddleOCR 3.3+ 的返回格式（rec_texts/rec_scores），确保 JSON 中写入 raw_text。

修改出处：
- ocr_tool/ocr/engine.py

---

时间：2026-02-06 20:09 +08:00

修改说明：
- 增加 OCR 预处理去水印开关（自适应阈值），用于减少水印误识别。
- CLI 增加 `--watermark-filter` 参数并同步文档。

修改出处：
- ocr_tool/ocr/engine.py
- ocr_tool/pipeline.py
- ocr_tool/models.py
- ocr_tool/cli.py
- PROJECT_GUIDE.md

---

时间：2026-02-06 20:31 +08:00

修改说明：
- 参考官方文档补充 OCR 参数调节能力（检测阈值/识别阈值/方向与矫正模块开关）。
- 用法文档补充调参示例。

修改出处：
- ocr_tool/models.py
- ocr_tool/cli.py
- ocr_tool/ocr/engine.py
- ocr_tool/pipeline.py
- PROJECT_GUIDE.md

---

时间：2026-02-06 20:35 +08:00

修改说明：
- 增强去水印预处理：基于低对比度连通域与稀疏大块区域做遮罩抹白。

修改出处：
- ocr_tool/ocr/engine.py

---

时间：2026-02-06 20:52 +08:00

修改说明：
- 新增 PaddleOCR-VL 引擎（可选 `--ocr-engine vl`），支持本地模型目录与 v1/v1.5 版本。
- VL 引擎采用整页识别并写入页面正文块。
- 文档补充 VL 用法与参数说明。

修改出处：
- ocr_tool/ocr/engine.py
- ocr_tool/pipeline.py
- ocr_tool/models.py
- ocr_tool/cli.py
- PROJECT_GUIDE.md
- requirements-ocr.txt

---

时间：2026-02-06 21:24 +08:00

修改说明：
- 支持通过 JSON 传入 PaddleOCR 产线高级参数，并在文档中说明用法。

修改出处：
- ocr_tool/cli.py
- ocr_tool/models.py
- ocr_tool/ocr/engine.py
- ocr_tool/pipeline.py
- PROJECT_GUIDE.md

---

时间：2026-02-06 21:35 +08:00

修改说明：
- 修复 CLI 语法错误（paddle_ocr_config 解析块位置与多余括号）。

修改出处：
- ocr_tool/cli.py

---

时间：2026-02-06 23:55 +08:00

修改说明：
- 清理所有 out* OCR 测试输出目录。

修改出处：
- 运行产物（out*）

---

时间：2026-02-07 00:42 +08:00

修改说明：
- 新增 AISTUDIO_TOKEN 到 .env，并在 test.py 中加载 .env。

修改出处：
- .env
- test.py

---

时间：2026-02-07 00:44 +08:00

修改说明：
- API 调用结果保存为 output/result.json 便于直接获取识别文本。

修改出处：
- test.py

---

时间：2026-02-07 00:47 +08:00

修改说明：
- 新增提取 block_content 的脚本（输出纯文本与 JSON 列表）。

修改出处：
- extract_block_content.py

---

时间：2026-02-07 00:50 +08:00

修改说明：
- 提供面向朗读的文本导出（按 block_order 排序并过滤非正文标签）。

修改出处：
- extract_block_content.py

---

时间：2026-02-07 01:05 +08:00

修改说明：
- 新增 AIStudio OCR API 引擎，支持从 API 返回的 block_content 拼接朗读文本。
- CLI 增加 AIStudio 参数，并将配置贯通到 pipeline。
- 用法文档补充 AIStudio 使用与 .env 配置说明。

修改出处：
- ocr_tool/ocr/aistudio.py
- ocr_tool/ocr/engine.py
- ocr_tool/models.py
- ocr_tool/cli.py
- ocr_tool/pipeline.py
- PROJECT_GUIDE.md

---

时间：2026-02-07 01:20 +08:00

修改说明：
- 重写 JSON 解析脚本，统一解析页面元信息与 parsing_res_list。
- 用法文档补充 JSON 字段说明与脚本输出。

修改出处：
- extract_block_content.py
- PROJECT_GUIDE.md

---

时间：2026-02-07 01:28 +08:00

修改说明：
- DeepSeek 默认模型改为 `deepseek-chat`（可通过环境变量覆盖）。
- 文档示例同步更新。

修改出处：
- ocr_tool/proofreading/deepseek.py
- PROJECT_GUIDE.md

---

时间：2026-02-07 01:33 +08:00

修改说明：
- DeepSeek 每批处理页数默认改为 10（可通过 CLI 参数调整）。

修改出处：
- ocr_tool/cli.py
- ocr_tool/models.py
- PROJECT_GUIDE.md

---

时间：2026-02-07 01:46 +08:00

修改说明：
- AIStudio 模式下按 parsing_res_list 构建文本块，并将原始返回写入每页 JSON。
- DeepSeek 校对改为使用解析后的 block_content（不再直接使用原始 JSON）。

修改出处：
- ocr_tool/ocr/aistudio.py
- ocr_tool/ocr/engine.py
- ocr_tool/pipeline.py
- PROJECT_GUIDE.md

---

时间：2026-02-07 02:05 +08:00

修改说明：
- DeepSeek 每批处理页数默认还原为 15。

修改出处：
- ocr_tool/cli.py
- ocr_tool/models.py
- PROJECT_GUIDE.md

---

时间：2026-02-07 02:18 +08:00

修改说明：
- 新增按批处理页面能力（默认每批 20 页）。

修改出处：
- ocr_tool/models.py
- ocr_tool/cli.py
- ocr_tool/pipeline.py
- PROJECT_GUIDE.md

---

时间：2026-02-07 02:32 +08:00

修改说明：
- DeepSeek prompt 重构，统一规则并强化图注/参考文献删除。
- 增加本地文本规则：图注与参考文献内容直接过滤。

修改出处：
- ocr_tool/proofreading/deepseek.py
- ocr_tool/filtering/apply.py

---

时间：2026-02-07 02:32 +08:00

修改说明：
- 新增限制处理总页数的参数（`--max-pages`）。

修改出处：
- ocr_tool/models.py
- ocr_tool/cli.py
- ocr_tool/pipeline.py
- PROJECT_GUIDE.md

---

时间：2026-02-07 02:45 +08:00

修改说明：
- DeepSeek prompt 增加删除版权页/出版印刷信息/免责声明/ISBN/CIP 等规则。

修改出处：
- ocr_tool/proofreading/deepseek.py

---

时间：2026-02-07 02:58 +08:00

修改说明：
- 新增 DeepSeek 后处理脚本：删除参考文献/出版信息并优化段落结构。

修改出处：
- post_process_output.py

---

时间：2026-02-07 03:08 +08:00

修改说明：
- 后处理脚本增加按 token 拆分与更小默认批次，避免单次输出过长。
- tokenizer 脚本支持统计 token 并给出建议批大小。

修改出处：
- post_process_output.py
- token/deepseek_tokenizer.py

---

时间：2026-02-07 03:16 +08:00

修改说明：
- 补充后处理与 tokenizer 使用说明。

修改出处：
- PROJECT_GUIDE.md
