export const MESSAGE_ACTIONS = {
    CALL_MAIN_FUNCTION: 'CALL_MAIN_FUNCTION',
};

export const TASK_TYPES = {
    FORCE_ENTER: 'FORCE_ENTER',
    CLEAR_COOKIES: 'CLEAR_COOKIES',
    UPDATE_CONFIG: 'UPDATE_CONFIG',
    GET_CONFIG: 'GET_CONFIG',
    UPDATE_PAGE_SIZE: 'UPDATE_PAGE_SIZE',
    GET_VCODE_TOKEN: 'GET_VCODE_TOKEN',
    CAPTCHA_RECOGNIZE: 'CAPTCHA_RECOGNIZE',
    CAPTCHA_TEST: 'CAPTCHA_TEST',
    GET_SAVED_LOGIN_STATUS: 'GET_SAVED_LOGIN_STATUS',
    LOOP_BATCH_SELECT_RELOGIN: 'LOOP_BATCH_SELECT_RELOGIN',
    LOGIN_WITH_VCODE: 'LOGIN_WITH_VCODE',
    CLEAR_SAVED_LOGIN: 'CLEAR_SAVED_LOGIN',
    GET_DIAGNOSTICS: 'GET_DIAGNOSTICS',
};

export const ERROR_CODES = {
    TAB_NOT_FOUND: 'TAB_NOT_FOUND',
    INVALID_PAYLOAD: 'INVALID_PAYLOAD',
    UNKNOWN_TASK: 'UNKNOWN_TASK',
    TASK_EXECUTION_FAILED: 'TASK_EXECUTION_FAILED',
    MESSAGE_SEND_FAILED: 'MESSAGE_SEND_FAILED',
    BAD_RESPONSE_SHAPE: 'BAD_RESPONSE_SHAPE',
    CAPTCHA_IMAGE_URL_REQUIRED: 'CAPTCHA_IMAGE_URL_REQUIRED',
    CAPTCHA_PROVIDER_INVALID: 'CAPTCHA_PROVIDER_INVALID',
    CAPTCHA_RECOGNIZE_FAILED: 'CAPTCHA_RECOGNIZE_FAILED',
};

export function createRequestId() {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function createTaskError(code, message, details = null) {
    const error = new Error(message);
    error.code = code;
    error.details = details;
    return error;
}

export function createOkResponse({ requestId, data = null }) {
    return {
        ok: true,
        requestId,
        data,
        error: null,
    };
}

export function createErrorResponse({ requestId, code, message, details = null }) {
    return {
        ok: false,
        requestId,
        data: null,
        error: {
            code,
            message,
            details,
        },
    };
}
