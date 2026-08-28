# 离线工具

NNU 博雅课自动化入口为 nnu_boya_automation.py，默认查询仙林校区和仙林新北校区；使用 `--watch --auto-select --yes --need-book 0/1` 时只持续轮询仙林，默认每 1 秒检查一次，直到当前轮次已选博雅理论课达到 4 门。watch 模式使用固定屏幕 TUI 展示运行时长、接口健康、轮询次数和任务进展，不会连续刷屏。计数只认 `XGXK`/`publicCourseType*` 博雅标识，不会把普通课程计入目标数。可选从 Windows 凭据管理器自动填入学号和密码，但每次启动仍要求本人完成验证码/人机认证。安装、运行和安全闸门见 选课/06_报告/博雅课自动化脚本说明.md。

在可见 Windows 终端中直接运行下面的命令即可进入鼠标配置 TUI，无需预先拼接参数：

~~~powershell
python 选课/05_工具/nnu_boya_automation.py
~~~

配置页会在打开登录浏览器前让你选择监控/自动选课模式、校区、目标课程、教材、登录填充、轮询和分页参数；模式按钮和“完整预设”按钮都会加载一整套可审计的中文配置，`[*]` 表示当前模式；确认后点击“应用并启动”。

### 中文 TUI 与完整预设

点击“模式 A｜自动选课”会加载自动选课完整预设：只查询 `XGXK` 博雅理论课、请求校区锁定仙林（2）、轮询间隔 1 秒、分页/校区请求间隔 0.5 秒、每页 50 条、单轮最多 50 页、登录等待 300 秒、启用凭据自动填充、教材默认不订、关闭快照；发现无冲突、未满、未选且当前已选博雅理论课少于 4 门时才提交。点击“模式 W｜只监控”会加载同样的查询性能参数，但请求校区为仙林（2）和仙林新北（4），并关闭自动提交。

预设加载后仍可点击中文配置行调整普通参数：教材在“不订购/订购”之间切换，轮询、请求间隔、每页数量、最大页数和登录等待可点击或滚轮循环，登录填充和快照可点击切换；“恢复当前模式预设”或键盘 `R` 可恢复整套值。安全规则（无冲突、未满、未选、容量复核）、自动模式的仙林校区和自动确认是保护闸门，界面明确显示“锁定”，不允许通过误操作关闭。验证码/人机认证始终由本人完成。

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

如果需要传统逐行输出（例如重定向到日志文件），可添加 `--plain-output`；该选项只关闭 TUI，不改变查询或提交逻辑。

TUI 还会显示浏览器当前页面校区与脚本实际请求校区、实际/期望教学班类型、目标选择器、冲突/满班/已选容量规则、教材选项、确认方式、轮询/请求/分页/超时参数、候选数量和提交统计。命令行提供初始值，配置页可在启动前调整，便于审计启动配置和实际请求范围。

启动 watch 模式后会先进入可操作配置页：Windows 控制台支持鼠标点击中文按钮行、滚轮调整数值；快捷键为 `S/W` 模式、`R` 恢复预设、`E` 目标、`2/4` 校区、`B` 教材、`I/D/P/M/T` 参数、`L` 登录填充、`Y` 确认、`O` 快照、`X` 实验班；目标行可输入 `auto`、`watch`、`id:<教学班ID>`、`number:<课程号>` 或 `name:<课程名>`，点击“应用并启动”后才打开登录浏览器；`Q`/`Esc` 取消，回车或 `A` 应用。自动选课的提交校区和安全规则为锁定项，避免误改为不安全请求。

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
