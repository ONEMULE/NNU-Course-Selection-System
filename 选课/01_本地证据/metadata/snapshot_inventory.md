# 本地快照登记

原始副本位于 `01_本地证据/raw/`，脱敏副本位于 `01_本地证据/sanitized/`。哈希见 `file_manifest.csv`。

| 快照 | 来源 URL（令牌已隐藏） | 页面版本线索 | 资源文件数 | HTML 大小 | 课程行数 | 活跃标签 |
|---|---|---|---:|---:|---:|---|
| 选课 | https://xsxk.nnu.edu.cn/xsxkapp/sys/xsxkapp/*default/grablessons.do?token=[REDACTED_TOKEN] | https://res.nnu.edu.cn/ver/1.8.1_TR13/products/jwfw/xsxkapp | 37 | 104837 | 27 | 博雅教育课程 |
| 选课点击后 | https://xsxk.nnu.edu.cn/xsxkapp/sys/xsxkapp/*default/grablessons.do?token=[REDACTED_TOKEN] | https://res.nnu.edu.cn/ver/1.8.1_TR13/products/jwfw/xsxkapp | 38 | 105579 | 27 | 博雅教育课程 |
| 选课失败弹窗 | https://xsxk.nnu.edu.cn/xsxkapp/sys/xsxkapp/*default/grablessons.do?token=[REDACTED_TOKEN] | https://res.nnu.edu.cn/ver/1.8.1_TR13/products/jwfw/xsxkapp | 38 | 105605 | 27 | 博雅教育课程 |

## 已确认的页面指纹

- `BaseUrl`: `https://xsxk.nnu.edu.cn:443/xsxkapp`。
- `loginType`: `ldap`。
- `resUrl`: `https://res.nnu.edu.cn/ver/1.8.1_TR13/products/jwfw/xsxkapp`。
- 页面版权行：`© 2016 江苏金智教育信息股份有限公司`，并出现 `苏ICP备10204514号`。
- 页面标签包含系统推荐、跨年级、跨专业、博雅、重修、体育、辅修、微专业和全校课程查询。
- 页面快照有浏览器扩展注入的 `redeviation-bs-*` 标记；这属于采集环境噪声，分析产品前端时应单独排除。
