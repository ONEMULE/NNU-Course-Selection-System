# 端点目录与调用语义

完整候选路径见 `endpoint_inventory.csv`。下表是依据本地前端包装函数整理出的首轮静态目录；请求参数只记录字段名，不记录具体账号、令牌、课程或批次值。

## 页面入口

| 路径 | 证据位置 | 说明 |
|---|---|---|
| `/sys/xsxkapp/*default/index.do` | 页面跳转/失效登录处理 | 登录或回到主页 |
| `/sys/xsxkapp/*default/grablessons.do` | 页面 URL/标签链接 | 选课主页面 |
| `/sys/xsxkapp/*default/selectedcourse.do` | `sidebar.js`/页面跳转 | 已选结果页面 |
| `/sys/xsxkapp/*default/selectedvolunteer.do` | `sidebar.js` | 已选志愿页面入口 |
| `/sys/xsxkapp/*default/departurelog.do` | `departurelog.js` | 结果/退选日志页面 |
| `/sys/xsxkapp/*default/curriculum.do` | `sidebar.js` | 课表页面 |
| `/sys/xsxkapp/*default/expcurriculum.do` | `sidebar.js` | 导出课表入口 |

## 身份、公共信息与轮次

| 方法（静态代码） | 路径 | 主要参数/状态 |
|---|---|---|
| GET | `/sys/xsxkapp/student/{studentCode}.do` | 学生信息；路径段来自当前学生代码 |
| GET | `/sys/xsxkapp/student/4/vcode.do` | 验证码/令牌前置数据线索 |
| GET | `/sys/xsxkapp/student/register.do` | 单点登录后的注册，查询参数 `number` |
| GET | `/sys/xsxkapp/elective/batch.do` | 选课批次/轮次 |
| POST | `/sys/xsxkapp/elective/batchisopen.do` | 查询轮次是否开放，参数含 `xklcdm` |
| GET | `/sys/xsxkapp/elective/volunteered.do` | 已选志愿概览 |
| GET | `/sys/xsxkapp/publicinfo.do` | 公共信息 |
| GET | `/sys/xsxkapp/publicinfo/dictionary.do` | 字典数据 |
| GET（同步） | `/sys/xsxkapp/publicinfo/sysparam.do` | 系统参数/功能开关 |
| GET | `/sys/xsxkapp/publicinfo/onlineUsers.do` | 在线人数提示 |

## 课程查询与详情

| 方法 | 路径 | 主要输入形态 |
|---|---|---|
| POST | `/sys/xsxkapp/elective/recommendedCourse.do` | 查询设置对象 |
| GET | `/sys/xsxkapp/elective/course.do` | 侧边栏搜索，带时间戳 |
| POST | `/sys/xsxkapp/elective/publicCourse.do` | 公选课查询 |
| POST | `/sys/xsxkapp/elective/programCourse.do` | 方案内课程查询 |
| POST | `/sys/xsxkapp/elective/testCourse.do` | 实验课程详情/选课前检查 |
| POST | `/sys/xsxkapp/elective/queryCourse.do` | 通用教学班查询 |
| POST | `/sys/xsxkapp/elective/course/kcssfa.do` | 课程所属方案 |
| GET | `/sys/xsxkapp/publicinfo/queryjxb.do` | 教学班详情，参数 `xklcdm/jxbid` |
| GET | `/sys/xsxkapp/elective/teachingclass/capacity.do` | 容量刷新，参数含教学班、校区/容量后缀和学生代码 |
| GET | `/sys/xsxkapp/util/canchoose.do` | 选课资格/可选性检查 |

## 选课、退选与结果

| 方法 | 路径 | 前端包装/输入形态 |
|---|---|---|
| POST | `/sys/xsxkapp/elective/volunteer.do` | `addParam`，内部数据含操作类型、学生、批次、教学班、校区、教学班类型等 |
| GET | `/sys/xsxkapp/elective/deleteVolunteer.do` | `deleteParam`，退选请求 |
| GET | `/sys/xsxkapp/elective/courseResult.do` | 已选课程结果 |
| GET | `/sys/xsxkapp/elective/payResult.do` | 缴费选课结果 |
| POST | `/sys/xsxkapp/elective/studentstatus.do` | 异步操作状态轮询；返回状态码 `1/-1` 参与前端判断 |
| GET | `/sys/xsxkapp/elective/returnResults.do` | 操作/退选结果日志 |
| GET | `/sys/xsxkapp/elective/unsuccessful.do` | 落选课程提示，参数含是否已读、学生、批次 |
| POST/GET（由代码路径分别调用） | `/sys/xsxkapp/elective/submit/unsuccessful.do` | 提交落选提示处理，参数含 `wids` 和学生代码 |
| GET | `/sys/xsxkapp/elective/queryStudentQueue.do` | 学生队列信息 |

## 横向分析重点

1. 对同一 `volunteer.do` 比较请求包装层、字段名、响应 `code/msg/data/dataList` 结构和异步状态轮询，而不是直接复用任何自动化逻辑。
2. 对登录模块只比较公开代码中的流程和状态管理；验证码、密码和会话值均不进入资料库。
3. 将 `xkxf.do`、`guideMap.do`、`textbook/*`、`publicinfo/fx|wzy|zx/*` 作为次级功能单独归档。
