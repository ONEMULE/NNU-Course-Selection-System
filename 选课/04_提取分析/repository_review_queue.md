# 仓库静态复核队列

排名仅按本地源码中的字符串命中计算，用于安排人工阅读顺序，不代表代码质量、当前可用性或对 NNU 的实际兼容性。所有仓库都不执行。

| 顺序 | 仓库 | 分组 | xsxkapp 文件 | volunteer.do 文件 | vcode 文件 | NNU 域名文件 | 评分 |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | treehey/AutoCaptcha | 02_adjacent | 2 | 0 | 0 | 0 | 106 |
| 2 | GreenTeodoro839/NJU-xk-helper | 01_same_stack | 9 | 5 | 1 | 0 | 68 |
| 3 | neiro-o/seuGrabber | 01_same_stack | 7 | 5 | 0 | 0 | 61 |
| 4 | lvttt/xdu-course-helper | 02_adjacent | 10 | 0 | 0 | 0 | 50 |
| 5 | Hz162/XJTU-Course-Genius | 02_adjacent | 5 | 2 | 0 | 0 | 49 |
| 6 | Weeye-hua/SZU-Course-Help | 01_same_stack | 4 | 2 | 1 | 0 | 39 |
| 7 | guiyi886/szu_grab_course | 01_same_stack | 4 | 2 | 1 | 0 | 39 |
| 8 | Lewin671/YourLesson | 01_same_stack | 4 | 2 | 1 | 0 | 39 |
| 9 | cells114514/JNU- | 02_adjacent | 4 | 1 | 0 | 0 | 28 |
| 10 | YHalo-wyh/YNU-xk_spider-Pro | 01_same_stack | 1 | 2 | 1 | 0 | 28 |
| 11 | ANDYWANGTIANTIAN/SZU_AutoCourseSelecter | 01_same_stack | 3 | 1 | 1 | 0 | 26 |
| 12 | XingHeYuZhuan/shiguang_warehouse | 00_nnu_direct | 0 | 0 | 0 | 4 | 26 |
| 13 | RyanShaw3/MyScripts | 02_adjacent | 3 | 2 | 0 | 0 | 23 |
| 14 | starwingcc/YNU-xk_spider | 01_same_stack | 3 | 1 | 0 | 0 | 23 |
| 15 | tonglinggejimo/Course-Monitor-Grabber | 01_same_stack | 2 | 2 | 1 | 0 | 23 |
| 16 | Bocchi-Hero/xjtu-seat-monitor | 02_adjacent | 2 | 1 | 0 | 0 | 22 |
| 17 | another-le/xjtu-tools | 02_adjacent | 3 | 0 | 0 | 0 | 21 |
| 18 | WheretoSleepinNJU/NJU-Class-Shedule-Flutter | 02_adjacent | 4 | 0 | 0 | 0 | 20 |
| 19 | TheFunny233/NJUClassGrabber | 01_same_stack | 1 | 2 | 1 | 0 | 20 |
| 20 | Dytchem/Machine-Learning-with-Python | 02_adjacent | 3 | 1 | 0 | 0 | 19 |
| 21 | KrowFeather/Prism | 02_adjacent | 2 | 1 | 1 | 0 | 19 |
| 22 | mbmcmzh/JNU_CourseSnatcher | 01_same_stack | 1 | 2 | 0 | 0 | 19 |
| 23 | KW10-2/Gadgets | 02_adjacent | 2 | 2 | 0 | 0 | 18 |
| 24 | davidwushi1145/YNU-xk_spider_Refactoring | 01_same_stack | 2 | 1 | 0 | 0 | 18 |
| 25 | AriaPokotengYe/SEU-NewSystem-catcher | 01_same_stack | 1 | 1 | 1 | 0 | 18 |

## 人工复核字段

- `base URL`、登录/验证码路径、请求方法和请求头处理。
- 轮次/批次字段、课程查询 `querySetting` 结构和教学班字段。
- `volunteer.do`、退选和结果轮询的请求/响应模型。
- 令牌、Cookie、密码、验证码和个人标识的处理方式；只记录模式，不复制值。
- 许可证、依赖、更新时间和明显的版本漂移。
