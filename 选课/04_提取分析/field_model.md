# 字段模型（静态提取版）

这些字段名来自本地前端脚本的对象访问和参数构造。它们是待验证的数据模型，不代表所有字段在每个接口都必填。

## 请求上下文

| 对象/包装 | 字段 |
|---|---|
| 会话/页面 | `token`, `studentCode`, `electiveBatchCode`, `teachingClassType`, `campus`, `teachCampus`, `isMajor` |
| 查询分页 | `querySetting`, `data`, `pageSize`, `pageNumber`, `order` |
| 选课操作 | `operationType`, `teachingClassId`, `needBook`, `testTeachingClassID`；添加包裹为 `addParam`，删除包裹为 `deleteParam` |
| 详情查询 | `xklcdm`, `jxbid`, `courseNumber`, `capacitySuffix`, `xh` |

## 学生/轮次/系统状态

- 学生：`code`, `gender`, `campus`, `teachCampus`, `electiveBatch`, `electiveBatchList`, `expElectiveBatchList`, `name`, `grade`, `collegeName`, `departmentName`, `totalCredit`, `needCredit`, `getCredit`, `getCreditProportion`。
- 轮次：`code`, `batchType`, `tacticCode`, `typeCode`, `canSelect`, `needConfirm`, `isConfirmed`, `confirmInfo`, `multiCampus`, `multiTeachCampus`。
- 规则/豁免：`noCheckTimeConflict`, `refreshNoCheckTimeConflict`, `retakeNoCheckTimeConflict`, `retakeNoCheckClassCapacity`, `noCheckExamTime`。
- 页面开关：`displayTJKC`, `displayFANKC`, `displayFAWKC`, `displayCXKC`, `displayTYKC`, `displayFX`, `displayWZYKC`, `displayXGXK`, `displayALLKC`, `displayCjMenu`, `needBook`, `kclbNotDisplay`, `displayMajorFlag`, `isSplitRetake`。

## 课程/教学班

- 课程层：`courseNumber`, `courseName`, `replaceCourseNumber`, `replaceCourseName`, `courseTypeName`, `courseNatureName`, `publicCourseTypeName`, `publicCourseTypeName2`, `departmentName`, `credit`, `hours`, `courseIndex`, `sportName`, `majorFlag`。
- 教学班层：`teachingClassID`, `teacherName`, `teacher`, `subTeacher`, `teachingPlace`, `time`, `courseSection`, `campus`, `teachCampus`, `capacitySuffix`, `courseUrl`。
- 容量/资格：`classCapacity`, `numberOfSelected`, `numberOfFirstVolunteer`, `capacityOfMale`, `capacityOfFemale`, `numberOfMale`, `numberOfFemale`, `limitGender`, `isFull`, `canOperate`, `canSelect`, `inQuene`/`inQueue`。
- 冲突/实验/教材：`isConflict`, `conflictDesc`, `hasTest`, `testTeachingClassID`, `needBook`, `canSelectBook`, `canDeleteBook`, `retakeType`, `retakeTypeDetail`。
- 志愿与结果：`volunteerIndex`, `tacticCode`, `isChoose`, `isTest`, `isNeedPay`, `paymentStatus`, `bookParam`。

## 响应外壳与状态

前端普遍读取 `code`、`msg`、`data`、`dataList` 和 `totalCount`。部分流程将 `code == '1'` 视作成功，将 `code == '302'` 视作登录态失效；异步操作状态还读取 `1/-1`。后续分析应把不同接口的状态码分别建模，不能把这些值直接推广到所有路径。
