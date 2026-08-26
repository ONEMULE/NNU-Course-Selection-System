// background/index.js
import { handleForceEnter, handleClearCookies } from './tasks/entrance';
import { handleUpdateConfig, handleGetConfig, handleUpdatePageSize } from './tasks/config';
import { getVcodeToken } from './tasks/vcode';
import {
    handleLoginWithVcode,
    handleClearSavedLogin,
    handleGetSavedLoginStatus,
    handleLoopBatchSelectRelogin,
} from './tasks/login';
import { handleCaptchaRecognize } from './tasks/captcha-recognize';
import { handleCaptchaTest } from './tasks/captcha-test';
import { handleGetDiagnostics } from './tasks/diagnostics';
import {
    MESSAGE_ACTIONS,
    TASK_TYPES,
    ERROR_CODES,
    createTaskError,
    createOkResponse,
    createErrorResponse,
    createRequestId,
} from '../shared/contract';
import { logDebug, logError } from '../shared/logger';
import { isSupportedCourseUrl } from '../shared/site-support';

// 当用户点击扩展图标时触发
chrome.action.onClicked.addListener((tab) => {
    chrome.sidePanel.open({ tabId: tab.id });
});

async function updateSidePanelState(tabId, url) {
    if (!url) return;

    const isCourseSite = isSupportedCourseUrl(url);

    if (isCourseSite) {
        // 目标网站：启用侧边栏
        await chrome.sidePanel.setOptions({
            tabId,
            path: 'index.html',
            enabled: true,
        });
    } else {
        // 非目标网站：禁用
        await chrome.sidePanel.setOptions({
            tabId,
            enabled: false,
        });
    }
}

// 监听标签页更新
chrome.tabs.onUpdated.addListener(async (tabId, info, tab) => {
    if (info.status === 'complete') {
        await updateSidePanelState(tabId, tab.url);
    }
});

// 监听标签页切换
chrome.tabs.onActivated.addListener(async (activeInfo) => {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    await updateSidePanelState(activeInfo.tabId, tab.url);
});

const TASK_HANDLER_MAP = {
    [TASK_TYPES.FORCE_ENTER]: handleForceEnter,
    [TASK_TYPES.CLEAR_COOKIES]: handleClearCookies,
    [TASK_TYPES.UPDATE_CONFIG]: handleUpdateConfig,
    [TASK_TYPES.GET_CONFIG]: handleGetConfig,
    [TASK_TYPES.UPDATE_PAGE_SIZE]: handleUpdatePageSize,
    [TASK_TYPES.GET_VCODE_TOKEN]: getVcodeToken,
    [TASK_TYPES.CAPTCHA_RECOGNIZE]: handleCaptchaRecognize,
    [TASK_TYPES.CAPTCHA_TEST]: handleCaptchaTest,
    [TASK_TYPES.GET_SAVED_LOGIN_STATUS]: handleGetSavedLoginStatus,
    [TASK_TYPES.LOOP_BATCH_SELECT_RELOGIN]: handleLoopBatchSelectRelogin,
    [TASK_TYPES.LOGIN_WITH_VCODE]: handleLoginWithVcode,
    [TASK_TYPES.CLEAR_SAVED_LOGIN]: handleClearSavedLogin,
    [TASK_TYPES.GET_DIAGNOSTICS]: handleGetDiagnostics,
};

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const { action, tabId, payload } = message;

    if (action === MESSAGE_ACTIONS.CALL_MAIN_FUNCTION) {
        const requestId = message.requestId || createRequestId();

        // 异步执行分发逻辑
        dispatchTask(tabId ?? sender?.tab?.id, payload)
            .then((result) => {
                sendResponse(createOkResponse({ requestId, data: result }));
            })
            .catch((err) => {
                logError('background', 'Task dispatch failed', {
                    requestId,
                    action,
                    taskType: payload?.taskType,
                    tabId,
                    code: err?.code,
                    message: err?.message,
                });
                sendResponse(
                    createErrorResponse({
                        requestId,
                        code: err?.code || ERROR_CODES.TASK_EXECUTION_FAILED,
                        message: err?.message || 'Task execution failed',
                        details: err?.details || null,
                    })
                );
            });

        return true; // 保持异步连接
    }
});

async function dispatchTask(tabId, payload = {}) {
    if (!tabId && tabId !== 0) {
        throw createTaskError(ERROR_CODES.TAB_NOT_FOUND, 'Current tab was not found');
    }

    const { taskType, data } = payload;
    if (!taskType) {
        throw createTaskError(ERROR_CODES.INVALID_PAYLOAD, 'Task payload is invalid');
    }

    const handler = TASK_HANDLER_MAP[taskType];
    if (!handler) {
        throw createTaskError(ERROR_CODES.UNKNOWN_TASK, `Unknown task type: ${taskType}`, {
            taskType,
        });
    }

    logDebug('background', 'Dispatching task', { tabId, taskType });

    try {
        return await handler(tabId, data);
    } catch (error) {
        if (error?.code) {
            throw error;
        }
        throw createTaskError(
            ERROR_CODES.TASK_EXECUTION_FAILED,
            error?.message || 'Task execution failed',
            { taskType }
        );
    }
}
