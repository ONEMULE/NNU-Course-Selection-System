export const PAGE_BRIDGE_MESSAGE_TYPES = {
    REQUEST: 'XDU_COURSE_HELPER_BRIDGE_REQUEST',
    RESPONSE: 'XDU_COURSE_HELPER_BRIDGE_RESPONSE',
};

export const PAGE_BRIDGE_SOURCE = 'xdu-course-helper';

export function createPageBridgeRequestMessage({ requestId, taskType, data = {} }) {
    return {
        source: PAGE_BRIDGE_SOURCE,
        type: PAGE_BRIDGE_MESSAGE_TYPES.REQUEST,
        payload: {
            requestId,
            taskType,
            data,
        },
    };
}

export function createPageBridgeResponseMessage({ requestId, response }) {
    return {
        source: PAGE_BRIDGE_SOURCE,
        type: PAGE_BRIDGE_MESSAGE_TYPES.RESPONSE,
        payload: {
            requestId,
            response,
        },
    };
}

export function isPageBridgeRequestMessage(message) {
    return (
        message?.source === PAGE_BRIDGE_SOURCE &&
        message?.type === PAGE_BRIDGE_MESSAGE_TYPES.REQUEST &&
        Boolean(message?.payload?.requestId) &&
        Boolean(message?.payload?.taskType)
    );
}

export function isPageBridgeResponseMessage(message, requestId) {
    return (
        message?.source === PAGE_BRIDGE_SOURCE &&
        message?.type === PAGE_BRIDGE_MESSAGE_TYPES.RESPONSE &&
        message?.payload?.requestId === requestId
    );
}

export function createPageBridgeClient({
    selfSource,
    createRequestId,
    postMessage,
    addMessageListener,
    removeMessageListener,
}) {
    return {
        send(taskType, data = {}) {
            const requestId = createRequestId();

            return new Promise((resolve) => {
                const handleMessage = (event) => {
                    if (event?.source !== selfSource) {
                        return;
                    }
                    if (!isPageBridgeResponseMessage(event?.data, requestId)) {
                        return;
                    }

                    removeMessageListener(handleMessage);
                    resolve(event.data.payload.response);
                };

                addMessageListener(handleMessage);
                postMessage(createPageBridgeRequestMessage({ requestId, taskType, data }));
            });
        },
    };
}
