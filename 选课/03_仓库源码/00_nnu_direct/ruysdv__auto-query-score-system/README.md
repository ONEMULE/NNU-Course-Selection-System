# 教务系统成绩监控通知系统

这是一个基于Python和Selenium开发的自动化工具，用于监控正方教务系统的成绩更新，并通过iOS Bark服务实时推送通知到你的iPhone。

## ✨ 功能特性

- 🤖 **自动登录**：自动处理教务系统登录流程，包括统一身份认证
- 📊 **成绩监控**：定时检查成绩更新，自动提取课程信息
- 📱 **实时通知**：通过iOS Bark推送新成绩通知
- 🔄 **定时检查**：每1分钟自动检查一次
- 🧹 **自动清理**：定期清理旧记录，优化存储空间
- ⚠️ **异常告警**：程序运行异常时自动发送错误通知
- 🌙 **后台运行**：无头模式，不影响电脑正常使用

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/仓库名.git
cd 仓库名
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

#### 3.1 复制配置模板

```bash
# Windows系统
copy .env.example .env

# Linux/Mac系统
cp .env.example .env
```

#### 3.2 编辑配置文件

用文本编辑器打开`.env`文件，填入你的信息：

```env
# 教务系统配置
SCHOOL_URL=https://jwxt.scnu.edu.cn/xtgl/login_slogin.html
SCHOOL_USERNAME=你的学号
SCHOOL_PASSWORD=你的教务系统密码

# Bark通知配置
BARK_SERVER=https://api.day.app
BARK_KEY=你的Bark密钥
```

**如何获取Bark密钥？**
1. 在App Store搜索并安装"Bark"应用
2. 打开Bark应用，自动获取设备专属密钥
3. 将密钥填入`BARK_KEY`字段

### 4. 运行程序

```bash
python selenium_login.py
```

程序将在后台运行，每1分钟检查一次成绩更新。

## 📋 支持的院校

本脚本适用于使用**正方教务系统**的院校。以下是已测试支持的院校列表：

### 综合类院校
- 浙江大学：`https://jwxt.zju.edu.cn`
- 上海交通大学：`https://jwxt.sjtu.edu.cn`
- 武汉大学：`http://jwxt.whu.edu.cn`
- 中山大学：`https://uems.sysu.edu.cn`
- 山东大学：`https://jwxt.sdu.edu.cn`
- 吉林大学：`https://jwxt.jlu.edu.cn`
- 四川大学：`https://jwxt.scu.edu.cn`
- 兰州大学：`https://jwxt.lzu.edu.cn`

### 师范类院校
- 华南师范大学：`https://jwxt.scnu.edu.cn`
- 华中师范大学：`https://jwxt.ccnu.edu.cn`
- 南京师范大学：`https://jwxt.njnu.edu.cn`
- 湖南师范大学：`https://jwxt.hunnu.edu.cn`
- 东北师范大学：`https://jwxt.nenu.edu.cn`
- 首都师范大学：`https://jwxt.cnu.edu.cn`
- 福建师范大学：`https://jwxt.fjnu.edu.cn`
- 山东师范大学：`https://jwxt.sdnu.edu.cn`

### 理工类院校
- 中国矿业大学：`https://jwxt.cumt.edu.cn`
- 南京理工大学：`https://jwxt.njust.edu.cn`
- 西南交通大学：`https://jwxt.swjtu.edu.cn`
- 西安电子科技大学：`https://jwxt.xidian.edu.cn`
- 哈尔滨工业大学：`https://jwxt.hit.edu.cn`
- 北京理工大学：`https://jwxt.bit.edu.cn`
- 大连理工大学：`https://jwxt.dlut.edu.cn`
- 电子科技大学：`https://jwxt.uestc.edu.cn`

### 财经类院校
- 中央财经大学：`https://jwxt.cufe.edu.cn`
- 上海财经大学：`https://jwxt.shufe.edu.cn`
- 中南财经政法大学：`https://jwxt.znufe.edu.cn`
- 东北财经大学：`https://jwxt.dufe.edu.cn`
- 江西财经大学：`https://jwxt.jxufe.edu.cn`
- 山东财经大学：`https://jwxt.sdufe.edu.cn`

### 医药类院校
- 南京医科大学：`https://jwxt.njmu.edu.cn`
- 广州医科大学：`https://jwxt.gzhmu.edu.cn`

### 农林类院校
- 华南农业大学：`https://jwxt.scau.edu.cn`
- 南京农业大学：`https://jwxt.njau.edu.cn`
- 西北农林科技大学：`https://jwxt.nwsuaf.edu.cn`

### 艺术类院校
- 中国美术学院：`https://jwxt.caa.edu.cn`
- 上海戏剧学院：`https://jwxt.sta.edu.cn`

### 其他类型院校
- 中国计量大学现代科技学院：`http://ywjw.cjlu.edu.cn`
- 湛江科技学院：`https://newjwxt.zjkju.edu.cn`
- 成都银杏酒店管理学院：`http://jwxt.gingkoc.edu.cn`

> **注意**：如果你的院校不在列表中，但使用的是正方教务系统，本脚本也可能适用。请根据实际情况调整`.env`文件中的`SCHOOL_URL`。

## 📁 项目结构

```
.
├── selenium_login.py      # 主程序文件
├── .env.example          # 配置模板（可上传）
├── .gitignore           # Git忽略规则
├── requirements.txt     # Python依赖
├── test_bark.py         # Bark测试脚本
└── README.md            # 项目说明
```

> **注意**：`.env`和`saved_courses.json`会被自动忽略，不会上传到GitHub

## ❓ 常见问题

### Q: 收不到Bark通知？

**A**: 检查以下几点：
- Bark应用是否在后台运行
- `.env`文件中的`BARK_KEY`是否正确
- 网络连接是否正常
- 尝试运行`python test_bark.py`测试通知功能

### Q: 登录失败？

**A**: 检查以下几点：
- 学号和密码是否正确
- `SCHOOL_URL`是否为学校教务系统的正确地址
- 学校教务系统是否正常开放
- 如页面结构变化，可能需要调整元素定位

### Q: 程序运行一段时间后停止？

**A**: 可能原因：
- 网络连接不稳定
- 教务系统会话过期
- 建议添加异常重试机制或使用进程守护工具

### Q: 如何停止程序？

**A**: 在终端按 `Ctrl + C` 停止运行

## 🔧 技术实现

- **自动化**：Selenium WebDriver
- **数据解析**：正则表达式 + 元素定位
- **数据存储**：JSON文件持久化
- **通知服务**：iOS Bark API
- **定时任务**：time.sleep循环
- **配置管理**：python-dotenv

## ⚠️ 注意事项

1. **安全第一**：
   - `.env`文件包含敏感信息，不要分享给他人
   - 定期检查程序运行状态
   - 建议使用强密码

2. **使用规范**：
   - 仅供个人学习使用
   - 遵守学校相关规定
   - 合理设置检查频率，避免给服务器造成压力

3. **环境要求**：
   - Python 3.7+
   - Chrome浏览器
   - 稳定的网络连接

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

本项目仅供学习和个人使用，请遵守相关法律法规。

---

**享受自动化带来的便利吧！** 🎉
