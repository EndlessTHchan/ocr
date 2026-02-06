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
