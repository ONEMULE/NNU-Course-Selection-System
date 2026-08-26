# 前端模块地图

证据来源：`01_本地证据/sanitized/选课点击后/选课点击后_files/`。这是基于静态脚本和 HTML 的功能地图，不代表已经对真实系统主动验证。

## 页面级配置

| 变量 | 本地快照值/形态 | 含义 |
|---|---|---|
| `BaseUrl` | `https://xsxk.nnu.edu.cn:443/xsxkapp` | 选课应用基地址 |
| `resUrl` | `https://res.nnu.edu.cn/ver/1.8.1_TR13/products/jwfw/xsxkapp` | 静态资源版本线索 |
| `loginType` | `ldap` | 登录形态线索 |
| `pageType` | `grablessons` | 当前页面类型 |
| `sessionStorage.token` | 使用但不保留实际值 | 请求头中的会话/页面令牌来源 |

## 脚本加载与责任

| 脚本 | 主要责任 | 关键函数/对象 |
|---|---|---|
| `bh_utils.js` | AJAX、同步 AJAX、窗口/提示、通用 DOM 工具 | `BH_UTILS.doAjax`, `BH_UTILS.doSyncAjax` |
| `indexBS.js` | 学生信息、轮次、公共信息、字典、系统参数、验证码令牌、登出 | `queryStudentInformation`, `queryTestBatch`, `querySysParam`, `queryVocdeToken` |
| `xsxkpub.js` | 选课公共请求包装、轮次确认、队列、落选提醒、操作状态轮询 | `queryRecommendedCourse`, `queryPublicCourse`, `queryProgramCourse`, `addVolunteer`, `queryOperateProcess` |
| `grablessons.js` | 课程列表、课程卡片、校区/冲突/容量判断、添加或删除志愿、实验课入口 | `buildQueryTCParam`, `buildAddVolunteerParam`, `selectPublicCourse` |
| `grablessonsBS.js` | 教学班容量刷新 | `queryTeachingClassCapacity` |
| `sidebar.js` | 侧边栏、轮次切换、学生资料、队列/落选/课表入口 | `openElectiveBatchWindow`, `initStudentInformation`, `initMessageQueue` |
| `selectedcourse.js` | 已选课程结果页渲染、删除、缴费、教材交互 | `initCourseResultList`, `deleteCourseResult`, `payCourseResult` |
| `selectedcourseBS.js` | 已选结果、退选、缴费、教材请求包装 | `queryChooseCourse`, `deleteVolunteerResult`, `payResult` |
| `departurelog.js` / `departurelogBS.js` | 退选/操作结果日志页 | `queryStudentReturnResults`, `buildTableHtml` |
| `loginInUserRegister.js` | 单点登录后的学生注册/跳转/错误处理 | `loginInUserRegister` |

## 前端状态

- `token`：从 `sessionStorage` 读取，并通过 `BH_UTILS.doAjax` 的 `headers` 参数传递给多数业务请求。
- `studentInfo`：至少被引用到 `code`、`gender`、`campus`、`teachCampus`、`electiveBatch`、`electiveBatchList`、`expElectiveBatchList`。
- `electiveBatch/currentBatch`：被引用到 `code`、`batchType`、`tacticCode`、`canSelect`、`needConfirm`、`isConfirmed`、`multiCampus`、`multiTeachCampus`、冲突/容量豁免开关和菜单显示开关。
- `sysParam`：控制公选课名称、菜单、教材、课程类别展示和其他页面开关。
- `currentCampus`、`teachingClassType`、`electiveIsOpen`、`bookParam`：控制当前查询上下文和操作前置条件。

## 采集环境噪声

三份 HTML 被浏览器扩展注入了 `redeviation-bs-*` 和 `yomitan-*` 元素/样式；这些不属于选课产品本身，应从 DOM 差异、脚本依赖和版本判断中排除。`saved_resource.html` 也指向浏览器扩展的模板渲染页，`saved_resource(1).html` 为 `about:blank`。
