const PREFIX = '[xdu-course-helper]';

function shouldDebug() {
    return Boolean(import.meta?.env?.DEV);
}

function format(scope, message) {
    return `${PREFIX}[${scope}] ${message}`;
}

function withMeta(meta) {
    if (!meta || Object.keys(meta).length === 0) {
        return undefined;
    }
    return meta;
}

export function logInfo(scope, message, meta) {
    const payload = withMeta(meta);
    if (payload) {
        console.info(format(scope, message), payload);
        return;
    }
    console.info(format(scope, message));
}

export function logWarn(scope, message, meta) {
    const payload = withMeta(meta);
    if (payload) {
        console.warn(format(scope, message), payload);
        return;
    }
    console.warn(format(scope, message));
}

export function logError(scope, message, meta) {
    const payload = withMeta(meta);
    if (payload) {
        console.error(format(scope, message), payload);
        return;
    }
    console.error(format(scope, message));
}

export function logDebug(scope, message, meta) {
    if (!shouldDebug()) {
        return;
    }
    const payload = withMeta(meta);
    if (payload) {
        console.debug(format(scope, message), payload);
        return;
    }
    console.debug(format(scope, message));
}
