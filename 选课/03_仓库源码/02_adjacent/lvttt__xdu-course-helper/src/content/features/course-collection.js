import { installZeroGridHook } from '../hooks/zero-grid.js';
import { escapeHtml } from '../runtime/dom.js';
import { createPageBridgeClient } from '../runtime/page-bridge.js';
import { poll } from '../runtime/poll.js';
import { PAGE_STORAGE_KEYS } from '../../shared/storage-keys.js';
import { createCollectionGridColumns } from './course-collection-columns.js';
import {
    isCollectedCourse,
    resolveBulkCollectionSelection,
} from './course-collection-selection.js';
import {
    buildBatchSelectSummary,
    extractSelectedCourseIds,
    runBatchSelectQueue,
    splitBatchSelectCourses,
} from './course-collection-batch-select.js';
import { getCollectionActionNoticeConfig } from './course-collection-notice.js';
import {
    ERROR_CODES,
    MESSAGE_ACTIONS,
    TASK_TYPES,
    createRequestId,
} from '../../shared/contract.js';
import {
    normalizeBatchSelectIntervalMs,
    normalizeLoopBatchSelectIntervalMs,
} from '../../shared/ext-config.js';

const COLLECTION_STORAGE_KEY = PAGE_STORAGE_KEYS.COURSE_COLLECTION;

const TAB_INSERT_LIST = [
    {
        text: '已收藏课程',
        roleVal: 999,
        zeroGridContainerId: '#collectionGrid',
        formContainerId: 'ysckcGrid',
    },
];

const ZERO_GRID_INSERT_COLLECTION_LIST = [
    '#zynkcGrid',
    '#allCourseGrid',
    '#blcAllCourseGrid',
    '#ysckcGrid',
];

function ensureHelperState() {
    const helper = window.xdu_course_helper || {};
    if (!Array.isArray(helper.collectionData)) {
        helper.collectionData = [];
    }
    if (!Array.isArray(helper.selectedCoursesInCollection)) {
        helper.selectedCoursesInCollection = helper.isLoopBatchSelecting
            ? [...helper.loopBatchSelectTargetCourseIds]
            : [];
    }
    if (typeof helper.isLoopBatchSelecting !== 'boolean') {
        helper.isLoopBatchSelecting = false;
    }
    if (typeof helper.loopBatchSelectStopRequested !== 'boolean') {
        helper.loopBatchSelectStopRequested = false;
    }
    if (!Array.isArray(helper.loopBatchSelectTargetCourseIds)) {
        helper.loopBatchSelectTargetCourseIds = [];
    }
    if (!Array.isArray(helper.loopBatchSelectTargetCourses)) {
        helper.loopBatchSelectTargetCourses = [];
    }
    if (helper.loopBatchSelectSummary === undefined) {
        helper.loopBatchSelectSummary = null;
    }
    if (!Number.isInteger(helper.loopBatchSelectReloginFailureCount)) {
        helper.loopBatchSelectReloginFailureCount = 0;
    }
    window.xdu_course_helper = helper;
    return helper;
}

function getCollectionData() {
    try {
        const data = localStorage.getItem(COLLECTION_STORAGE_KEY);
        return data ? JSON.parse(data) : [];
    } catch (error) {
        console.error('选课助手: 读取收藏课程失败', error);
        return [];
    }
}

function saveCollectionData(collection) {
    localStorage.setItem(COLLECTION_STORAGE_KEY, JSON.stringify(collection));
}

function findUlElement() {
    const tabContainer = document.getElementById('xkTabContainer');
    return tabContainer ? tabContainer.querySelector('ul') : null;
}

function createAllPageArticle() {
    const originalArticle = $('<article>').addClass('cv-block-hide cv-pb-38').attr({
        role: 'kcfltab',
    });
    TAB_INSERT_LIST.forEach((tabInfo) => {
        const newArticle = $(originalArticle.clone(true));
        newArticle.attr('id', 'xk_containrt_' + tabInfo.roleVal);
        newArticle.append($('<div>').addClass('course_title'));
        newArticle.append(
            $('<div>')
                .addClass('cv-expert-mode')
                .attr({
                    id: tabInfo.zeroGridContainerId.replace('#', ''),
                    style: 'min-height: 550px;',
                })
        );
        $('#cvAside').before(newArticle);
    });
}

export function getCsrfToken(force = false) {
    const csrfToken = $('#csrfToken').val();
    if (csrfToken && !force) {
        return Promise.resolve(csrfToken);
    }
    return fetch(
        'https://yjsxk.xidian.edu.cn/yjsxkapp/sys/xsxkapp/xsxkHome/loadPublicInfo_course.do'
    )
        .then((response) => response.json())
        .then((data) => data?.csrfToken || null)
        .catch((error) => {
            console.error('Failed to fetch CSRF token:', error);
            return null;
        });
}

function submitCourse(data) {
    return fetch('https://yjsxk.xidian.edu.cn/yjsxkapp/sys/xsxkapp/xsxkCourse/choiceCourse.do', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams(data).toString(),
    }).then((response) => response.json());
}

function loadSelectedCourses() {
    return fetch(
        'https://yjsxk.xidian.edu.cn/yjsxkapp/sys/xsxkapp/xsxkCourse/loadStdCourseInfo.do',
        {
            method: 'GET',
        }
    ).then((response) => response.json());
}

function waitForMilliseconds(delayMs) {
    return new Promise((resolve) => {
        window.setTimeout(resolve, delayMs);
    });
}

function getBatchSelectIntervalMs() {
    const extConfig = window.xdu_course_helper?.getLocalStorage?.(PAGE_STORAGE_KEYS.EXT_CONFIG) || {};
    return normalizeBatchSelectIntervalMs(extConfig.batchSelectIntervalMs);
}

function getLoopBatchSelectIntervalMs() {
    const extConfig = window.xdu_course_helper?.getLocalStorage?.(PAGE_STORAGE_KEYS.EXT_CONFIG) || {};
    return normalizeLoopBatchSelectIntervalMs(extConfig.loopBatchSelectIntervalMs);
}

function hasSavedLoginInfo() {
    const loginInfo = window.xdu_course_helper?.getLocalStorage?.(PAGE_STORAGE_KEYS.LOGIN_INFO);
    return Boolean(loginInfo?.loginName && loginInfo?.loginPwd);
}

function setPageCsrfToken(csrfToken) {
    const csrfInput = document.getElementById('csrfToken');
    if (csrfInput) {
        csrfInput.value = csrfToken;
    }
}

async function sendLoopBackgroundTask(taskType, data = {}) {
    if (!window.xdu_course_helper?.pageBridgeClient) {
        window.xdu_course_helper = window.xdu_course_helper || {};
        window.xdu_course_helper.pageBridgeClient = createPageBridgeClient({
            selfSource: window,
            createRequestId,
            postMessage: (message) => window.postMessage(message, window.location.origin),
            addMessageListener: (listener) => window.addEventListener('message', listener),
            removeMessageListener: (listener) => window.removeEventListener('message', listener),
        });
    }

    return window.xdu_course_helper.pageBridgeClient.send(taskType, data);
}

export function shouldDisableCollectionActions({ isLoopBatchSelecting = false } = {}) {
    return Boolean(isLoopBatchSelecting);
}

export function shouldRetryLoopActionAfterRelogin({
    error,
    isLoopBatchSelecting = false,
} = {}) {
    return Boolean(isLoopBatchSelecting && error instanceof SyntaxError);
}

export function incrementLoopReloginFailureCount(helper) {
    const nextValue = Number(helper?.loopBatchSelectReloginFailureCount || 0) + 1;
    if (helper) {
        helper.loopBatchSelectReloginFailureCount = nextValue;
    }
    return nextValue;
}

export function resetLoopReloginFailureCount(helper) {
    if (helper) {
        helper.loopBatchSelectReloginFailureCount = 0;
    }
    return 0;
}

export async function retryLoopActionWithRelogin({
    action,
    relogin,
    refreshCsrfToken,
    helper,
    isLoopBatchSelecting = false,
}) {
    try {
        return {
            ok: true,
            value: await action(),
        };
    } catch (error) {
        if (!shouldRetryLoopActionAfterRelogin({ error, isLoopBatchSelecting })) {
            throw error;
        }

        let reloginResponse;
        try {
            reloginResponse = await relogin();
        } catch (reloginError) {
            reloginResponse = {
                ok: false,
                error: {
                    code: reloginError?.code || '',
                    message: reloginError?.message || '自动重新登录失败',
                },
            };
        }

        if (reloginResponse?.ok === false && reloginResponse?.error?.code === ERROR_CODES.CAPTCHA_RECOGNIZE_FAILED) {
            return {
                ok: false,
                fatal: true,
                message: '验证码识别服务全部失败，已停止循环批量选课',
            };
        }

        if (reloginResponse?.ok !== true || reloginResponse?.data?.code !== '1') {
            const failureCount = incrementLoopReloginFailureCount(helper);
            return {
                ok: false,
                fatal: failureCount >= 5,
                message:
                    failureCount >= 5
                        ? '自动重新登录连续失败 5 次，已停止循环批量选课'
                        : `自动重新登录失败，等待下一轮重试（${failureCount}/5）`,
            };
        }

        resetLoopReloginFailureCount(helper);
        const nextCsrfToken = await refreshCsrfToken();
        if (!nextCsrfToken) {
            return {
                ok: false,
                fatal: true,
                message: '重新登录成功，但刷新 csrfToken 失败，已停止循环批量选课',
            };
        }

        return {
            ok: true,
            value: await action(),
        };
    }
}

export async function runLoopBatchSelect({
    executeRound,
    wait = async () => {},
    intervalMs,
    shouldStop = () => false,
    onRoundComplete = () => {},
}) {
    let latestSummary = null;

    while (true) {
        latestSummary = await executeRound();
        onRoundComplete(latestSummary);

        if (shouldStop() || latestSummary?.fatalError || latestSummary?.isAllTargetsCompleted) {
            return latestSummary;
        }

        await wait(intervalMs);

        if (shouldStop()) {
            return latestSummary;
        }
    }
}

function showBatchSelectResult({
    successCourses = [],
    failureCourses = [],
    skippedCourses = [],
    notice = '',
} = {}) {
    const modalId = 'xdu-helper-result-modal';
    $(`#${modalId}`).remove();

    const total = successCourses.length + failureCourses.length + skippedCourses.length;
    const modalHtml = `
        <div id="${modalId}" style="z-index: 999999; position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.4); backdrop-filter: blur(4px); font-family: system-ui, -apple-system, sans-serif;">
            <div style="background: white; width: 520px; max-width: 95%; border-radius: 16px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25); overflow: hidden; animation: xduSlideUp 0.3s ease-out;">
                <div style="padding: 20px 24px; border-bottom: 1px solid #f0f0f0; display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; font-size: 18px; font-weight: 700; color: #111827;">批量选课结果报告</h3>
                    <span style="font-size: 13px; background: #f3f4f6; color: #6b7280; padding: 4px 10px; border-radius: 20px;">共处理 ${total} 门</span>
                </div>

                <div style="padding: 24px; max-height: 450px; overflow-y: auto;">
                    ${
                        notice
                            ? `
                        <div style="background: #fff7d6; border: 1px solid #f2c94c; padding: 12px; border-radius: 8px; margin-bottom: 16px;">
                            <p style="margin: 0; font-size: 13px; color: #8a5a00; line-height: 1.6;">
                                ${escapeHtml(notice)}
                            </p>
                        </div>
                    `
                            : ''
                    }
                    ${
                        successCourses.length > 0
                            ? `
                        <div style="margin-bottom: 24px;">
                            <div style="display: flex; align-items: center; gap: 8px; color: #059669; font-size: 15px; font-weight: 700; margin-bottom: 12px;">
                                <span>🚀 已成功提交队列 (${successCourses.length})</span>
                            </div>
                            <div style="background: #ecfdf5; border: 1px solid #d1fae5; padding: 12px; border-radius: 8px; margin-bottom: 12px;">
                                <p style="margin: 0; font-size: 12px; color: #065f46; line-height: 1.5;">
                                    💡 提示：队列提交成功不代表最终选上，请务必前往<b>“已选课程”</b>页面确认最终结果。
                                </p>
                            </div>
                            <div style="display: flex; flex-wrap: wrap; gap: 12px;">
                                ${successCourses
                                    .map((name) => {
                                        const safeName = escapeHtml(name);
                                        return `
                                    <div style="width: calc(50% - 6px); background: #f9fafb; border: 1px solid #e5e7eb; padding: 10px; border-radius: 8px; box-sizing: border-box;">
                                        <div style="font-size: 13px; color: #374151; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${safeName}">${safeName}</div>
                                    </div>
                                `;
                                    })
                                    .join('')}
                            </div>
                        </div>
                    `
                            : ''
                    }

                    ${
                        skippedCourses.length > 0
                            ? `
                        <div style="margin-bottom: ${failureCourses.length > 0 ? '24px' : '0'};">
                            <div style="display: flex; align-items: center; gap: 8px; color: #b7791f; font-size: 15px; font-weight: 700; margin-bottom: 12px;">
                                <span>⏭️ 已自动跳过 (${skippedCourses.length})</span>
                            </div>
                            <div style="background: #fffaf0; border: 1px solid #f6d365; padding: 12px; border-radius: 8px; margin-bottom: 12px;">
                                <p style="margin: 0; font-size: 12px; color: #975a16; line-height: 1.5;">
                                    这些课程已存在于<b>“已选课程”</b>中，本次未重复提交。
                                </p>
                            </div>
                            <div style="display: flex; flex-wrap: wrap; gap: 12px;">
                                ${skippedCourses
                                    .map((name) => {
                                        const safeName = escapeHtml(name);
                                        return `
                                    <div style="width: calc(50% - 6px); background: #fffaf0; border: 1px solid #f6e05e; padding: 10px; border-radius: 8px; box-sizing: border-box;">
                                        <div style="font-size: 13px; color: #744210; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${safeName}">${safeName}</div>
                                    </div>
                                `;
                                    })
                                    .join('')}
                            </div>
                        </div>
                    `
                            : ''
                    }

                    ${
                        failureCourses.length > 0
                            ? `
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px; color: #dc2626; font-size: 15px; font-weight: 700; margin-bottom: 12px;">
                                <span>❌ 提交失败 (${failureCourses.length})</span>
                            </div>
                            <div style="display: flex; flex-wrap: wrap; gap: 12px;">
                                ${failureCourses
                                    .map((item) => {
                                        const safeCourseName = escapeHtml(item.courseName);
                                        const safeMessage = escapeHtml(item.message);
                                        return `
                                    <div style="width: calc(50% - 6px); background: #fef2f2; border: 1px solid #fee2e2; padding: 10px; border-radius: 8px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between;">
                                        <div style="font-size: 13px; font-weight: 700; color: #991b1b; margin-bottom: 4px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">${safeCourseName}</div>
                                        <div style="font-size: 11px; color: #b91c1c; opacity: 0.8;">原因: ${safeMessage}</div>
                                    </div>
                                `;
                                    })
                                    .join('')}
                            </div>
                        </div>
                    `
                            : ''
                    }
                </div>

                <div style="padding: 16px 24px; background: #f9fafb; border-top: 1px solid #f0f0f0; text-align: right;">
                    <button id="xdu-close-modal" style="padding: 10px 28px; background: #2563eb; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);">
                        我知道了
                    </button>
                </div>
            </div>
        </div>

        <style>
            @keyframes xduSlideUp {
                from {
                    opacity: 0;
                    transform: translateY(20px) scale(0.98);
                }
                to {
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }
            }
            #xdu-close-modal:hover {
                background: #1d4ed8 !important;
                transform: translateY(-1px);
                box-shadow: 0 6px 12px -2px rgba(37, 99, 235, 0.3);
            }
            #xdu-close-modal:active {
                transform: translateY(0);
            }
        </style>
    `;

    $('body').append(modalHtml);

    $('#xdu-close-modal').on('click', function () {
        $(`#${modalId}`).fadeOut(200, function () {
            $(this).remove();
        });
    });
}

export function initCourseCollectionFeature() {
    const helper = ensureHelperState();

    function loadCollectionData() {
        helper.collectionData = getCollectionData();
    }

    function addCourseToCollection(course) {
        if (!course?.BJDM) {
            return;
        }

        const index = helper.collectionData.findIndex((item) => item.BJDM === course.BJDM);
        if (index !== -1) {
            helper.collectionData[index] = course;
        } else {
            helper.collectionData.push(course);
        }
        saveCollectionData(helper.collectionData);
    }

    function removeCourseFromCollection(bjdm) {
        helper.collectionData = helper.collectionData.filter((item) => item.BJDM !== bjdm);
        saveCollectionData(helper.collectionData);
    }

    function changeAllCheckboxInCollection(status) {
        const checkboxElements = $.find('input[xk-checkbox]');
        const selection = resolveBulkCollectionSelection(
            checkboxElements.map((el) => el.getAttribute('data-bjdm')),
            helper.collectionData,
            status
        );

        helper.selectedCoursesInCollection = selection.selectedCourseIds;
        checkboxElements.forEach((el) => {
            const bjdm = el.getAttribute('data-bjdm');
            el.checked = Boolean(selection.checkedStateById[bjdm]);
        });
    }

    function getSelectedCoursesInCollection() {
        const selectedCourses = [];
        $.find('input[xk-checkbox]:checked').forEach((el) => {
            const bjdm = el.getAttribute('data-bjdm');
            const course = helper.collectionData.find((item) => item.BJDM === bjdm);
            if (course) {
                selectedCourses.push(course);
            }
        });
        return selectedCourses;
    }

    async function executeBatchSelectRound(courses) {
        if (courses.length === 0) {
            return buildBatchSelectSummary({
                queueResult: { successCourses: [], failureCourses: [], successfulCourseIds: [] },
                skippedCourses: [],
                targetCourseIds: [],
                successfulCourseIds: [],
            });
        }

        const targetCourseIds = courses.map((course) => course.BJDM).filter(Boolean);
        let csrfToken = await getCsrfToken();
        if (!csrfToken) {
            return buildBatchSelectSummary({
                queueResult: {
                    successCourses: [],
                    failureCourses: [
                        {
                            courseName: '全部课程',
                            message: '获取 csrfToken 失败',
                        },
                    ],
                    successfulCourseIds: [],
                },
                skippedCourses: [],
                targetCourseIds,
                successfulCourseIds: [],
                fatalError: '获取 csrfToken 失败',
            });
        }

        setPageCsrfToken(csrfToken);

        const refreshCsrfToken = async () => {
            const nextCsrfToken = await getCsrfToken(true);
            if (!nextCsrfToken) {
                return null;
            }
            csrfToken = nextCsrfToken;
            setPageCsrfToken(nextCsrfToken);
            return nextCsrfToken;
        };

        const relogin = async () =>
            sendLoopBackgroundTask(TASK_TYPES.LOOP_BATCH_SELECT_RELOGIN);

        let pendingCourses = courses;
        let skippedCourses = [];
        try {
            const selectedCourseResponseResult = await retryLoopActionWithRelogin({
                action: () => loadSelectedCourses(),
                relogin,
                refreshCsrfToken,
                helper,
                isLoopBatchSelecting: helper.isLoopBatchSelecting,
            });
            if (!selectedCourseResponseResult.ok) {
                return buildBatchSelectSummary({
                    queueResult: {
                        successCourses: [],
                        failureCourses: [
                            {
                                courseName: '循环批量选课',
                                message: selectedCourseResponseResult.message,
                            },
                        ],
                        successfulCourseIds: [],
                        fatalError: selectedCourseResponseResult.fatal
                            ? selectedCourseResponseResult.message
                            : null,
                    },
                    skippedCourses: [],
                    targetCourseIds,
                    successfulCourseIds: [],
                    fatalError: selectedCourseResponseResult.fatal
                        ? selectedCourseResponseResult.message
                        : null,
                });
            }
            const selectedCourseResponse = selectedCourseResponseResult.value;
            const selectedCourseIds = extractSelectedCourseIds(selectedCourseResponse);
            const splitResult = splitBatchSelectCourses(courses, selectedCourseIds);
            pendingCourses = splitResult.pendingCourses;
            skippedCourses = splitResult.skippedCourses;
        } catch (error) {
            console.warn('选课助手: 查询已选课程失败，继续执行批量选课', error);
        }

        if (pendingCourses.length === 0) {
            return buildBatchSelectSummary({
                queueResult: { successCourses: [], failureCourses: [], successfulCourseIds: [] },
                skippedCourses,
                targetCourseIds,
                successfulCourseIds: [],
            });
        }

        console.log('选课助手: 批量提交选课队列开始');
        const intervalMs = getBatchSelectIntervalMs();
        const queueResult = await runBatchSelectQueue(pendingCourses, {
            intervalMs,
            submitCourse: async (course) => {
                const submitResult = await retryLoopActionWithRelogin({
                    action: () => submitCourse({ bjdm: course.BJDM, csrfToken }),
                    relogin,
                    refreshCsrfToken,
                    helper,
                    isLoopBatchSelecting: helper.isLoopBatchSelecting,
                });
                if (submitResult.ok) {
                    return submitResult.value;
                }

                const stopError = new Error(submitResult.message);
                stopError.stopQueue = true;
                stopError.courseName = course.KCMC;
                stopError.fatalError = submitResult.fatal ? submitResult.message : null;
                throw stopError;
            },
            wait: waitForMilliseconds,
        });
        console.log('选课助手: 批量提交选课队列完成');

        return buildBatchSelectSummary({
            queueResult,
            skippedCourses,
            targetCourseIds,
            successfulCourseIds: queueResult.successfulCourseIds,
            fatalError: queueResult.fatalError,
        });
    }

    async function batchSelectCourses(courses) {
        if (courses.length === 0) {
            return;
        }

        const summary = await executeBatchSelectRound(courses);
        showBatchSelectResult(summary);
    }

    function collectionPageInit(tabInfo) {
        $('[role="kcfltab"]').toggleClass('cv-block-hide', true);
        $('#xk_containrt_' + tabInfo.roleVal).removeClass('cv-block-hide');
        $(tabInfo.zeroGridContainerId).html(`<div id="${tabInfo.formContainerId}"></div>`);
        const actionNotice = getCollectionActionNoticeConfig();

        const selectAllBtn = $('<button>')
            .addClass('cv-btn cv-btn-primary')
            .css({ width: '80px', height: '35px', marginRight: '10px' })
            .text('全选')
            .on('click', () => {
                changeAllCheckboxInCollection(true);
            });
        const deselectAllBtn = $('<button>')
            .addClass('cv-btn cv-btn-default')
            .css({ width: '80px', height: '35px', marginRight: '10px' })
            .text('全不选')
            .on('click', () => {
                changeAllCheckboxInCollection(false);
            });
        const batchSelectBtn = $('<button>')
            .addClass('cv-btn cv-btn-success')
            .css({ width: '80px', height: '35px', marginRight: '10px' })
            .text('批量选课')
            .on('click', () => {
                const selectedCourses = getSelectedCoursesInCollection();
                void batchSelectCourses(selectedCourses);
            });
        const loopBatchSelectBtn = $('<button>')
            .addClass('cv-btn cv-btn-danger')
            .css({ width: '110px', height: '35px' })
            .text(helper.isLoopBatchSelecting ? '停止循环' : '循环批量选课')
            .on('click', () => {
                if (helper.isLoopBatchSelecting) {
                    helper.loopBatchSelectStopRequested = true;
                    syncCollectionActionState();
                    return;
                }
                void startLoopBatchSelect();
            });

        const syncCollectionActionState = () => {
            const shouldDisable = shouldDisableCollectionActions(helper);
            selectAllBtn.prop('disabled', shouldDisable);
            deselectAllBtn.prop('disabled', shouldDisable);
            batchSelectBtn.prop('disabled', shouldDisable);
            loopBatchSelectBtn.text(helper.isLoopBatchSelecting ? '停止循环' : '循环批量选课');
            $.find('input[xk-checkbox]').forEach((el) => {
                el.disabled = shouldDisable;
            });
        };

        const createLoopFeedbackSummary = (summary, notice) => ({
            ...summary,
            notice: notice || summary?.notice || '',
        });

        async function startLoopBatchSelect() {
            if (!hasSavedLoginInfo()) {
                showBatchSelectResult({
                    successCourses: [],
                    skippedCourses: [],
                    failureCourses: [
                        {
                            courseName: '循环批量选课',
                            message: '未检测到已保存的账号密码，请先在侧边栏勾选记住账号密码并完成一次登录',
                        },
                    ],
                    notice: '',
                });
                return;
            }

            const selectedCourses = getSelectedCoursesInCollection();
            if (selectedCourses.length === 0) {
                showBatchSelectResult({
                    successCourses: [],
                    skippedCourses: [],
                    failureCourses: [],
                    notice: '请先勾选要循环批量选课的课程。',
                });
                return;
            }

            helper.isLoopBatchSelecting = true;
            helper.loopBatchSelectStopRequested = false;
            helper.loopBatchSelectTargetCourseIds = selectedCourses
                .map((course) => course.BJDM)
                .filter(Boolean);
            helper.loopBatchSelectTargetCourses = selectedCourses.map((course) => ({ ...course }));
            helper.loopBatchSelectSummary = null;
            syncCollectionActionState();

            let finalSummary = null;
            let stopRequested = false;

            try {
                finalSummary = await runLoopBatchSelect({
                    executeRound: async () => {
                        const roundSummary = await executeBatchSelectRound(
                            helper.loopBatchSelectTargetCourses
                        );
                        helper.loopBatchSelectSummary = roundSummary;
                        return roundSummary;
                    },
                    wait: waitForMilliseconds,
                    intervalMs: getLoopBatchSelectIntervalMs(),
                    shouldStop: () => helper.loopBatchSelectStopRequested,
                });
            } catch (error) {
                finalSummary = buildBatchSelectSummary({
                    queueResult: {
                        successCourses: [],
                        failureCourses: [
                            {
                                courseName: '循环批量选课',
                                message: error?.message || '循环批量选课执行失败',
                            },
                        ],
                        successfulCourseIds: [],
                    },
                    skippedCourses: [],
                    targetCourseIds: helper.loopBatchSelectTargetCourseIds,
                    successfulCourseIds: [],
                    fatalError: error?.message || '循环批量选课执行失败',
                });
            } finally {
                stopRequested = helper.loopBatchSelectStopRequested;
                helper.isLoopBatchSelecting = false;
                helper.loopBatchSelectStopRequested = false;
                helper.loopBatchSelectTargetCourseIds = [];
                helper.loopBatchSelectTargetCourses = [];
                helper.loopBatchSelectSummary = finalSummary;
                syncCollectionActionState();
            }

            if (!finalSummary) {
                return;
            }

            if (finalSummary.fatalError) {
                showBatchSelectResult(
                    createLoopFeedbackSummary(finalSummary, finalSummary.fatalError)
                );
                return;
            }

            if (finalSummary.isAllTargetsCompleted) {
                showBatchSelectResult(
                    createLoopFeedbackSummary(
                        finalSummary,
                        '当前勾选课程已全部完成，循环批量选课已自动停止。'
                    )
                );
                return;
            }

            if (stopRequested) {
                showBatchSelectResult(
                    createLoopFeedbackSummary(finalSummary, '循环批量选课已手动停止。')
                );
            }
        }

        const noticeContainer = $('<div>').css(actionNotice.style).text(actionNotice.text);
        const buttonContainer = $('<div>').css({ marginBottom: '15px' });
        buttonContainer
            .append(selectAllBtn)
            .append(deselectAllBtn)
            .append(batchSelectBtn)
            .append(loopBatchSelectBtn);
        $(tabInfo.zeroGridContainerId).prepend(buttonContainer).prepend(noticeContainer);

        window.courseTableFieldDefine.ysckcColumns = createCollectionGridColumns(
            window.courseTableFieldDefine.yxkcColumns,
            function (row) {
                const safeBjdm = escapeHtml(row.BJDM);
                return `<input type="checkbox" xk-checkbox data-bjdm="${safeBjdm}" />`;
            }
        );

        helper.selectedCoursesInCollection = [];

        new zeroGrid({
            container: '#' + tabInfo.formContainerId,
            dataKey: 'KCDM',
            columns: window.courseTableFieldDefine.ysckcColumns,
            datas: helper.collectionData,
            pageSize: window.WIS_XTCS.xkgl_xsxkmymrxsjls,
            loadAfterListener: function () {
                $.find('input[xk-checkbox]').forEach((el) => {
                    const bjdm = el.getAttribute('data-bjdm');
                    if (helper.selectedCoursesInCollection.includes(bjdm)) {
                        el.checked = true;
                    }
                    el.addEventListener('change', (event) => {
                        const selectedBjdm = event.currentTarget.getAttribute('data-bjdm');
                        if (event.currentTarget.checked) {
                            if (!isCollectedCourse(helper.collectionData, selectedBjdm)) {
                                event.currentTarget.checked = false;
                                return;
                            }
                            if (!helper.selectedCoursesInCollection.includes(selectedBjdm)) {
                                helper.selectedCoursesInCollection.push(selectedBjdm);
                            }
                            return;
                        }
                            helper.selectedCoursesInCollection =
                            helper.selectedCoursesInCollection.filter(
                                (item) => item !== selectedBjdm
                            );
                    });
                });
                syncCollectionActionState();
            },
        }).render();

        syncCollectionActionState();

        console.log(`选课助手: ${tabInfo.text}页面初始化完成`);
    }

    function createCustomTab(liEl) {
        if (!liEl) {
            return null;
        }

        const myLiList = [];
        for (const tabInfo of TAB_INSERT_LIST) {
            const myLiEl = liEl.cloneNode(true);
            const aEl = myLiEl.querySelector('a');
            Object.assign(aEl, {
                id: `xkkctab_${tabInfo.roleVal}`,
                style: '',
                textContent: tabInfo.text,
            });
            aEl.setAttribute('role-val', tabInfo.roleVal);
            aEl.setAttribute('role-title', tabInfo.text);
            aEl.setAttribute('show', 'true');
            aEl.addEventListener('click', function () {
                $('[cv-role="tab"]').parent().removeClass('cv-active');
                $(this).parent().addClass('cv-active');
                collectionPageInit(tabInfo);
            });
            myLiList.push(myLiEl);
        }

        return myLiList;
    }

    async function insertCustomTab() {
        try {
            const ulEl = await poll(findUlElement);
            const tabList = createCustomTab(ulEl.lastElementChild);
            if (tabList && tabList.length > 0) {
                tabList.forEach((tab) => ulEl.appendChild(tab));
                console.log('选课助手: 成功插入标签');
            }
        } catch (error) {
            console.warn('选课助手: 无法找到标签栏容器，停止尝试', error);
        }
    }

    function handleCollectionButtonClick(bjdm, isCollected) {
        if (isCollected) {
            removeCourseFromCollection(bjdm);
            helper.selectedCoursesInCollection = helper.selectedCoursesInCollection.filter(
                (item) => item !== bjdm
            );
        } else {
            const course = helper.zeroGridDatas?.datas?.find((item) => item.BJDM === bjdm);
            addCourseToCollection(course);
        }
        helper.zeroGridRenderDataFunc?.(helper.zeroGridDatas);
    }

    function insertCollectionButton(zeroGridInstance) {
        if (!ZERO_GRID_INSERT_COLLECTION_LIST.includes(zeroGridInstance.params.container)) {
            return;
        }
        if (zeroGridInstance.params.columns.some((col) => col.display === '收藏')) {
            return;
        }

        zeroGridInstance.params.columns.push({
            display: '收藏',
            width: '7%',
            align: 'center',
            view: function (row) {
                const isCollected = helper.collectionData.some((item) => item.BJDM === row.BJDM);
                const statusText = isCollected ? 'true' : 'false';
                const safeBjdm = escapeHtml(row.BJDM);
                return `<a class="zeromodal-btn zeromodal-btn-primary xkbtn" collection-button collection-status="${statusText}" data-bjdm="${safeBjdm}" href="javascript:void(0);">${isCollected ? '取消收藏' : '收藏'}</a>`;
            },
        });
    }

    function bindCollectionButtonEvent() {
        $.find('a[collection-button]').forEach((el) => {
            el.addEventListener('click', (event) => {
                const bjdm = event.currentTarget.getAttribute('data-bjdm');
                const isCollected =
                    event.currentTarget.getAttribute('collection-status') === 'true';
                handleCollectionButtonClick(bjdm, isCollected);
            });
        });
    }

    function hookZeroGrid() {
        installZeroGridHook({
            poll,
            onBeforeRender: (instance) => insertCollectionButton(instance),
            onAfterRender: (instance, renderData) => {
                bindCollectionButtonEvent();
                helper.zeroGridDatas = renderData;
                helper.zeroGridRenderDataFunc = instance.renderData.bind(instance);
            },
        })
            .then((installed) => {
                if (!installed) {
                    return;
                }
                console.log('选课助手: 成功找到 zeroGrid 对象并完成函数钩子');
            })
            .catch((error) => {
                console.warn('选课助手: 无法找到 zeroGrid 对象，无法进行函数钩子', error);
            });
    }

    insertCustomTab();
    loadCollectionData();
    hookZeroGrid();
    poll(() => window.$).then(() => {
        createAllPageArticle();
    });
}
