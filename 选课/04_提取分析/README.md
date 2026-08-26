# 提取分析区

当前已生成：

- `endpoint_inventory.csv`：本地前端提取的 57 个端点候选，查询值已去除/脱敏。
- `endpoint_catalog.md`：按页面、公共信息、课程查询、选课结果归类的静态目录。
- `field_model.md`：会话、轮次、课程、教学班、容量和结果字段模型。
- `frontend_module_map.md`：脚本加载顺序和模块责任。
- `snapshot_comparison.md`：三份本地快照的共性/差异。
- `repository_fingerprint_matrix.csv`：47 个公开仓库的字符串指纹统计。
- `repository_endpoint_hits.csv`：715 条仓库指纹命中位置，仅保留仓库/文件/行号/指纹。
- `repository_metadata.csv`：仓库 commit、时间、文件数、许可证文件和依赖清单。
- `repository_review_queue.md`：按静态相似度排出的人工阅读顺序。
- `sensitive_materials_scan.csv`：潜在敏感字段模式命中登记，不保存具体匹配行。
- `session_storage_inventory.csv`：脱敏脚本中的浏览器会话存储键、读写动作和证据位置。
- `snapshot_summary.csv` / `snapshot_article_summary.csv`：三份脱敏页面快照的结构统计。
- `static_call_graph.csv`：从页面初始化到查询、选退课、状态轮询和结果刷新的静态调用图。
- `source_correspondence_matrix.csv`：NNU 直接上下文与同栈公开源码的对应关系和结论边界。

这些结果都是静态证据，不应被解释为已经验证真实系统的当前接口或安全属性。
