export function extractSelectedCourseIds(responseData) {
    const results = Array.isArray(responseData?.results) ? responseData.results : [];
    return results.map((item) => item?.BJDM).filter(Boolean);
}

export function splitBatchSelectCourses(courses, selectedCourseIds) {
    const selectedCourseIdSet = new Set(selectedCourseIds);

    return courses.reduce(
        (result, course) => {
            if (selectedCourseIdSet.has(course.BJDM)) {
                result.skippedCourses.push(course);
                return result;
            }

            result.pendingCourses.push(course);
            return result;
        },
        { pendingCourses: [], skippedCourses: [] }
    );
}

export function buildBatchSelectSummary({
    queueResult,
    skippedCourses = [],
    targetCourseIds = [],
    successfulCourseIds = [],
    fatalError = null,
}) {
    const skippedCourseNames = skippedCourses.map((course) => course.KCMC);
    const completedCourseIds = Array.from(
        new Set([
            ...successfulCourseIds,
            ...skippedCourses.map((course) => course.BJDM).filter(Boolean),
        ])
    );
    const targetCourseIdSet = new Set(targetCourseIds);
    const completedTargetCount = completedCourseIds.filter((courseId) =>
        targetCourseIdSet.has(courseId)
    ).length;
    const isAllTargetsCompleted =
        targetCourseIds.length > 0 && completedTargetCount === targetCourseIds.length;

    return {
        successCourses: queueResult.successCourses,
        failureCourses: queueResult.failureCourses,
        skippedCourses: skippedCourseNames,
        completedCourseIds,
        isAllTargetsCompleted,
        fatalError,
        notice:
            skippedCourseNames.length > 0 &&
            queueResult.successCourses.length === 0 &&
            queueResult.failureCourses.length === 0
                ? '所有课程已经选择完毕'
                : '',
    };
}

export async function runBatchSelectQueue(
    courses,
    { intervalMs, submitCourse, wait = async () => {} }
) {
    const successCourses = [];
    const successfulCourseIds = [];
    const failureCourses = [];

    for (let index = 0; index < courses.length; index += 1) {
        const course = courses[index];

        try {
            const response = await submitCourse(course);
            if (response?.code === 1) {
                successCourses.push(course.KCMC);
                successfulCourseIds.push(course.BJDM);
            } else {
                failureCourses.push({
                    courseName: course.KCMC,
                    message: response?.msg || '选课请求失败',
                });
            }
        } catch (error) {
            if (error?.stopQueue) {
                failureCourses.push({
                    courseName: error?.courseName || course.KCMC,
                    message: error?.message || '选课请求失败',
                });
                return {
                    successCourses,
                    successfulCourseIds,
                    failureCourses,
                    fatalError: error?.fatalError || null,
                };
            }
            failureCourses.push({
                courseName: course.KCMC,
                message: '选课请求失败',
            });
        }

        if (index < courses.length - 1) {
            await wait(intervalMs);
        }
    }

    return {
        successCourses,
        successfulCourseIds,
        failureCourses,
        fatalError: null,
    };
}
