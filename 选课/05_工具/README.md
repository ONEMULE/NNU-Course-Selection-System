# 离线工具

NNU 博雅课自动化入口为 nnu_boya_automation.py，默认查询仙林校区和仙林新北校区；使用 `--watch --auto-select --yes --need-book 0/1` 时只持续轮询仙林，默认每 1 秒检查一次，直到当前轮次已选博雅理论课达到 4 门。计数只认 `XGXK`/`publicCourseType*` 博雅标识，不会把普通课程计入目标数。可选从 Windows 凭据管理器自动填入学号和密码，但每次启动仍要求本人完成验证码/人机认证。安装、运行和安全闸门见 选课/06_报告/博雅课自动化脚本说明.md。

## 只读采集

采集当前选课批次全校课程查询页（QXKC/queryCourse.do），脚本会按仙林和仙林新北两个校区上下文请求并合并重复课程；结果默认写入 `05_工具/.runtime/`，生成课程层级 JSON 和一行一个教学班的 CSV。返回列表可能包含当前批次中暂不可直接提交的教学班，`selectableNow` 仅是依据接口状态整理出的保守提示：

~~~powershell
python 选课/05_工具/nnu_boya_automation.py --collect-open-courses
~~~

也可以同时获取当前批次已选课程（courseResult.do），理论课和实验教学班会分开保存并建立关联：

~~~powershell
python 选课/05_工具/nnu_boya_automation.py --collect-open-courses --collect-selected-courses
~~~

指定输出目录或全校课程筛选条件：

~~~powershell
python 选课/05_工具/nnu_boya_automation.py `
  --collect-open-courses `
  --school-keyword "人工智能" `
  --school-category 01 `
  --school-unit 19 `
  --export-dir 选课/05_工具/.runtime
~~~

采集模式只读，不调用 `volunteer.do`；仍需本人在可见浏览器中完成登录和人机认证。采集结果可能包含个人当前课程安排，默认目录已加入 Git 忽略，不会推送到仓库。

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
