---
name: organize-files
description: 当用户上传文档并要求分类、重命名、查重、生成Excel清单或ZIP时，使用安全文件整理工具；先预览，确认后复制。
---

# 中文文件整理助手

先用一句中文说明正在使用本技能。读取仓库 AGENTS.md 并遵守原件保护规则。

1. 确定用户上传的实际文件路径。使用附件提供的工具取得文件；不要编造路径。若上传的是作为输入容器的 ZIP，使用 `import-zip` 解压到新的 `inbox/<任务>/`；普通待分类压缩包保留原样。其他压缩格式暂不自动解包，可以请用户上传 ZIP 或解压后的文件。
2. 从自然语言提取分类条件、分组方式和重命名规则。合理默认：按文件类型分类、保留文件名、全部保留重复文件、日期使用文件修改日期（上海时区）。用户要求文档日期/拍摄日期/创建日期时，不要用修改日期冒充；说明现有支持并澄清。不能读取到的内容标记为未识别。
3. 将规则保存在 `local-rules/<任务>.json`，具体语法见 README 和 examples/rules.json。用户未要求内容分类时不进行文本提取。用户文件及规则不得加入 Git。输出目录使用唯一任务编号。
4. 在仓库目录执行 `.venv/bin/python -m file_organizer preview <原件目录> --output outputs/<任务>-preview --rules local-rules/<任务>.json`。如果未安装，运行 `bash scripts/setup.sh`。
5. 查看 plan.json、errors.json 和各文件 warning。向用户用中文列出：文件总数、分类方式、重命名示例、重复组数、失败及内容未识别数；提供 preview.xlsx。明确这时未复制整理、没有删除原件。请求用户确认当前预览；不要提前执行 apply。
6. 用户确认后运行 `.venv/bin/python -m file_organizer apply outputs/<任务>-preview/plan.json --output outputs/<任务>-result --confirm`。不得手工修改 plan 绕过重新预览。失败则诊断，原件变化需重做预览；新尝试用新目录。
7. 读取执行结果和 errors.json，检查 ZIP 完整性及清单；交付 organized.zip、inventory.xlsx、duplicates.json、errors.json 和整理目录。通过当前客户端支持的附件方式或可点击本地文件链接提供下载。不要承诺用户未验证的远端下载链接。
8. 明确成功数、失败数和限制。重复只表示文件字节完全相同，不代表视觉/语义相同。无需 API 密钥，不使用外部 AI 服务解析私人文档。

本技能是自然语言与本地脚本之间的操作指引，不是独立聊天服务；用户在 Codex 中描述需求，代理负责调用工具。

## OCR扩展
当用户要求按图片或扫描PDF的文字分类时，读取同级 `../document-ocr/SKILL.md`，规则增加 `"ocr": true`。只读预览会在本地识别，向用户展示识别不确定性。整理复制仍保留原文件字节；可搜索PDF通过单独的 ocr-pdf 命令在确认后生成新副本。
