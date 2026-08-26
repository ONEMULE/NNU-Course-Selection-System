# 公开仓库源码区

这里仅放公开仓库的源码快照。所有仓库均视为不可信输入：不执行、不安装依赖、不运行构建脚本；分析应以文本检索、版本信息和人工审阅为主。

目录分组与采集清单中的 `category` 对应：

- `00_nnu_direct`：直接涉及 NNU/NJNU 或南师大教务入口的项目。
- `01_same_stack`：明确出现 `xsxkapp`、`volunteer.do`、`student/4/vcode.do` 等同栈指纹的项目。
- `02_adjacent`：相邻学校、历史版本、课表/登录/验证码辅助项目；只作对比证据。
- `03_unverified_or_failed`：仓库不存在、下载失败或内容待人工核验的条目。

每次采集后，在 `02_公开资料/repository_index/` 写入采集日志和每个仓库的 commit/哈希；不要把真实系统的 Cookie、token 或网络日志放进这些目录。
