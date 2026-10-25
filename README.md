# 文件整理助手

这是一个在 Codex 中使用的文件整理项目。**你只需上传文件并用中文说要求，不需要写代码。** Codex 会按仓库中的 AGENTS.md 和专用 `organize-files` 技能操作工具。

## 你以后怎么用

1. 在 Codex 中选择这个仓库和已发布的云环境，上传待整理文件（多文件可打成 ZIP）。
2. 发送例如：
   > 请整理我上传的文件：合同放一起，发票放一起，其他按文件类型分类，再按年份分文件夹。文件名加上日期和序号。找出重复文件，给我 Excel 清单。先给我预览，不要修改原件。
3. 查看助手给出的预览及无法识别的文件。满意后回复：
   > 确认这份预览，请复制整理并打包 ZIP，保留所有原件和重复文件。
4. 下载整理后的 ZIP 和 Excel 清单。若要改规则，直接说“把合同改成按月份分类，重新预览”。

也可以说：“只查重”“只生成清单，不整理”“按原文件名中的客户名分组”。助手会替你准备规则。没有明确要求时：按文件类型分组、保留文件名、以修改日期为日期。**文件名中的日期、拍摄日期、创建日期和文档签署日期不是同一回事**，需要特别说明。

## 支持范围

| 内容 | 当前能力 |
| --- | --- |
| Word、PDF、Excel、PPT、图片、压缩包及其他文件 | 按扩展名识别类型；按名称、修改日期分类；复制、改名、查重、清单、ZIP |
| DOCX | 读取段落和表格文本，按关键词分类 |
| PDF | 读取文本型 PDF；开启OCR可识别无文本页面；不读取加密PDF |
| XLSX / XLSM / XLS / CSV | 读取表格内容；不运行宏，公式使用已有缓存值 |
| PPTX | 读取文本框文字；图表、嵌入对象和图片文字不保证提取 |
| TXT / MD / JSON / LOG | UTF-8 或 GB18030 文本关键词分类 |
| PNG/JPEG/BMP/TIFF/WebP、扫描 PDF | 可开启本地中英文OCR，识别文字后按关键词分类 |
| DOC、PPT、压缩包内容，HEIC/SVG等 | 暂不进行旧格式转换、内部内容分类或OCR；记录提示并按其他条件整理 |

内容分类是可解释的关键词规则，不是自动语义理解。多项规则按顺序匹配第一项；同一规则中的不同条件同时满足，关键词列表内任意一个命中即可。未匹配文件按类型分类。大小超过30MB、Office解压内容超过100MB、PDF超过100页或文本超过20万字符会跳过内容读取并记录原因。大小限制不影响普通复制和哈希查重。

## 安全与结果

- 预览只读原件，生成 plan.json、preview.xlsx、duplicates.json、errors.json。
- 确认后仅复制到全新目录，保留扩展名，重名自动添加 `__2`、`__3` 等后缀。现有输出目录会被拒绝，避免覆盖。
- 使用 SHA-256 检查文件字节是否完全相同；相似照片、内容相同但格式不同的文档不会被当成重复。
- 复制时与预览的哈希比对，复制后再次校验；变化、损坏或读取失败会记录原因，不删除原件。
- ZIP 包含整理成功的文件、Excel 清单、重复清单及失败记录。失败的临时副本会被清理。
- Excel 包含名称、原路径、格式、字节大小、修改日期、分类、目标路径、哈希、状态和原因，并有重复文件及失败记录工作表。
- 符号链接和特殊文件跳过。不修改 Office 文件内容，不执行宏，不向第三方服务上传内容。不保证保留 ACL、扩展属性或创建时间；复制保留修改日期到秒。
- 运行期间请勿修改原件或输出目录；这不是对抗恶意输入的隔离沙箱。大批文件需预留约两倍文件总大小的空间供副本和ZIP。
- 用户资料存放在被 Git 忽略的 inbox/、outputs/、local-rules/ 中，不能提交到代码仓库。

## 给 Codex 的运行说明

Python 3.11+（已验证3.12），无需数据库、常驻服务或额外密钥。

```bash
bash scripts/setup.sh
# 上传 ZIP 作为一批输入时（不覆盖已有目录）
.venv/bin/python -m file_organizer import-zip batch.zip --output inbox/batch-001
# 默认分类预览
.venv/bin/python -m file_organizer preview inbox/batch-001 --output outputs/batch-001-preview
# 或使用规则预览
.venv/bin/python -m file_organizer preview inbox/batch-001 --output outputs/batch-002-preview --rules examples/rules.json
# 必须在用户确认相应预览之后执行
.venv/bin/python -m file_organizer apply outputs/batch-002-preview/plan.json --output outputs/batch-002-result --confirm
.venv/bin/python -m pytest -q
```

ZIP 输入导入最多10000项、总解压2GB、单文件512MB；拒绝路径穿越、符号链接、加密项及重复路径。不支持自动解包 RAR/7z，不递归解压。导入失败保留诊断记录，换新目录重试。

规则示例见 [examples/rules.json](examples/rules.json)。支持：

- `group_by`：按 `category`（分类）、`type`（类型）、`year`（年）、`month`（年月）依次建立目录；空列表为平铺。
- `rename`：可使用 `{stem}` 原文件名（不含扩展名）、`{index}` 四位序号、`{date}` 修改日期、`{category}` 分类、`{type}` 类型；程序自动保留扩展名。省略则保留原名（不适合跨平台的字符会替换）。
- `rules`：每项必须有 `category`；可用 `filename_contains`、`content_contains`、`extensions`（含点，如 `.pdf`）、`date_from` / `date_to`（含边界，YYYY-MM-DD）。
- `timezone`：默认 `Asia/Shanghai`。日期来自文件系统修改时间，上传过程可能改变它。

退出码：0流程完成，2部分文件失败，1整体失败。内容提取提示不会阻止复制，但必须向用户报告。

## 已配置的效率工具

- 仓库级 AGENTS.md：让 Codex 始终按中文、预览优先、保护原件的规则工作。
- 专用 `.agents/skills/organize-files/SKILL.md`：把自然语言整理需求转成可复用操作流程。
- 锁定版本的 Python 依赖、一键安装和测试脚本、自动化回归测试、GitHub Actions 测试配置。
- 无需购买额外插件或提供 API 密钥；无需你手动安装技能。已配置本地OCR扩展；旧版 Office 内容转换仍可后续按需扩展。

云环境配置的保存不等于发布；首次设置后，在环境设置中查看并保存配置，然后发布环境供以后任务复用。


## 新增：中文图片和扫描件识别

已经集成 [Tesseract](https://github.com/tesseract-ocr/tesseract)、[OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF)、[pytesseract](https://github.com/madmaze/pytesseract) 和 [pypdfium2](https://github.com/pypdfium2-team/pypdfium2)，以及本项目专用的 `document-ocr` 技能。它是为当前安全流程编写的技能，并非直接安装的 Anthropic 技能包。PaddleOCR、Docling、MarkItDown 暂未安装，避免功能重叠。

直接对 Codex 说：

> 请识别这些图片和扫描PDF里的文字，按合同、发票分类，先给我预览。识别不清楚的列出来。

或者：

> 我想让这份扫描PDF可以搜索文字。请先让我核对识别结果，确认后另存一份，保留原件。

- 简体中文、繁体中文、英文语言包已配置，识别在本地执行，不调用付费API或外部识别服务。
- 内容分类需要规则 `"ocr": true`；默认关闭。示例见 `examples/ocr-rules.json`。
- OCR可能出错，尤其是手写、模糊、旋转、印章和复杂表格。金额、日期和编号请人工核对。
- OCR模式限单文件30MB、PDF20页、位图2500万像素；单次识别45秒超时，可搜索PDF任务300秒超时。超限记录原因，不静默丢弃。
- 不支持加密PDF、HEIC/SVG、动画和多帧图片的OCR。已有文本的PDF页面不会再次识别其中图片，带文字页眉的扫描正文可能需要后续单独处理。
- 分类预览不会生成OCR替代文件；apply复制的仍是原始字节。可搜索PDF单独生成 `searchable.pdf`，同时记录原件和副本哈希、执行日志及失败原因。

代理操作示例：

```bash
.venv/bin/python -m file_organizer preview inbox/batch-001 --output outputs/batch-003-preview --rules examples/ocr-rules.json
# 用户确认生成可搜索PDF副本之后
.venv/bin/python -m file_organizer ocr-pdf inbox/batch-001/扫描件.pdf --output outputs/batch-003-ocr --confirm
```

新机器的系统依赖（当前云环境已有Tesseract和字体）：

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr fonts-noto-cjk
bash scripts/setup.sh
```

安装脚本自动获取固定版本的语言包并校验SHA-256，保存在不提交Git的 `.ocr/` 中；重复运行会验证并复用模型。模型来源为 [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast)，版本与校验值记录在 `scripts/setup_ocr.py`，依赖许可证以各上游项目为准。运行不需要联网，初次安装依赖和语言包需要网络。
