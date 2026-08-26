import { claimGuard } from './runtime/guard.js';
import {
    ERROR_CODES,
    MESSAGE_ACTIONS,
    TASK_TYPES,
    createErrorResponse,
} from '../shared/contract.js';
import {
    createPageBridgeResponseMessage,
    isPageBridgeRequestMessage,
} from './runtime/page-bridge.js';

const ALLOWED_PAGE_TASKS = new Set([TASK_TYPES.LOOP_BATCH_SELECT_RELOGIN]);

function postBridgeResponse(requestId, response) {
    window.postMessage(createPageBridgeResponseMessage({ requestId, response }), window.location.origin);
}

if (claimGuard('content:bridge:background-forwarder')) {
    window.addEventListener('message', async (event) => {
        if (event.source !== window) {
            return;
        }

        if (!isPageBridgeRequestMessage(event.data)) {
            return;
        }

        const { requestId, taskType, data } = event.data.payload;
        if (!ALLOWED_PAGE_TASKS.has(taskType)) {
            postBridgeResponse(
                requestId,
                createErrorResponse({
                    requestId,
                    code: ERROR_CODES.UNKNOWN_TASK,
                    message: `Bridge task is not allowed: ${taskType}`,
                })
            );
            return;
        }

        try {
            const response = await chrome.runtime.sendMessage({
                action: MESSAGE_ACTIONS.CALL_MAIN_FUNCTION,
                requestId,
                payload: {
                    taskType,
                    data,
                },
            });
            postBridgeResponse(requestId, response);
        } catch (error) {
            postBridgeResponse(
                requestId,
                createErrorResponse({
                    requestId,
                    code: ERROR_CODES.MESSAGE_SEND_FAILED,
                    message: error?.message || 'Bridge message failed',
                })
            );
        }
    });
}
