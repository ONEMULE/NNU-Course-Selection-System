# 离线工具

NNU 博雅课自动化入口为 nnu_boya_automation.py，只查询仙林校区和仙林新北校区；每次启动都要求人工重新登录和完成认证。安装、运行和安全闸门见 选课/06_报告/博雅课自动化脚本说明.md。

脚本均以本资料库为默认工作区，按以下顺序运行：

1. `sanitize_snapshots.ps1`：从 raw 复制出的 HTML 生成脱敏副本。
2. `extract_endpoints.ps1`：从脱敏 HTML/JS 提取端点候选。
3. `build_local_inventory.ps1`：生成快照登记、文件哈希和页面指纹摘要。
4. `collect_repositories.ps1 -IncludeP2`：浅克隆清单中的公开 GitHub 仓库；不会执行仓库代码，也不会重置已有 checkout。
5. `download_public_sources.ps1`：下载清单中的官方公开资料/Gist/GreasyFork 页面；NNU 真实入口按策略跳过。
6. `extract_official_pdfs.ps1`：用 Poppler 生成 PDF 文本和第一页预览。
7. `scan_repository_fingerprints.ps1`、`extract_repository_hits.ps1`：只读扫描源码字符串指纹。
8. `build_repository_metadata.ps1`、`build_review_queue.ps1`、`build_official_materials_index.ps1`：重建分析索引。
9. `scan_sensitive_materials.ps1`：登记潜在敏感字段模式，不输出匹配行。
10. `extract_static_analysis.ps1`：从脱敏页面/脚本生成 sessionStorage、快照结构、静态调用图和源码对应矩阵。

第三方代码目录永远按不可信输入处理；不要在该目录安装依赖、运行构建或执行脚本。
