# XJTU Course Genius v4.6.1

> 西安交通大学选课助手 — 基于 Flutter + Go 的跨平台桌面应用

## 功能

- **统一认证登录** — XJTU CAS/OAuth 登录，完整复刻原网页登录流程（MFA detect / 验证 / trustAgent）
- **自动续期** — session 过期自动 relogin，所有 xkfw API 调用自动恢复
- **选课操作** — 选课、退课、选课结果查询
- **跨平台** — Windows（.exe / 安装包）、Linux（.deb / .tar.gz）、macOS（.dmg）

## 安装

### Windows
- **安装包**: 运行 `XJTU-Course-Genius-Setup-v4.6.1.exe`
- **便携版**: 解压 `XJTU-Course-Genius-windows-x64.zip`，运行 `xjtu_course_genius.exe`

### macOS
- 挂载 `XJTU-Course-Genius-macos.dmg`，拖入 Applications 文件夹

### Linux
- Debian/Ubuntu: `sudo dpkg -i XJTU-Course-Genius-linux-x64.deb`
- 其他发行版: 解压 `XJTU-Course-Genius-linux-x64.tar.gz`

## 更新日志

### v4.6.1
- 修复 MFA 登录死锁：全新登录重置 failN（对齐浏览器语义），不再触发 CAS 强制验证码
- 修复 MFA state 一次性重用：登录失败后自动清除 state 并重新初始化
- 修复 MFA 页误跳转：只有服务器返回 success==true 才进入主界面
- MFA detect 请求补齐 `loginType=passwordLogin`（与原网页一致）
- MFA 完成登录固定携带 `trustAgent=true`（等价原网页勾选"信任此设备"，同设备 10 天内免验证）
- 修复 release body 为空：release job 增加 checkout 步骤，使用 RELEASE.md

### v4.6.0
- Session 过期自动 relogin（所有 xkfw API 调用）

### v4.5
- MFA + captcha 流程 overhaul
- CAS 登录流程文档
