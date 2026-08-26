export const DEFAULT_BATCH_SELECT_INTERVAL_MS = 800;
export const MIN_BATCH_SELECT_INTERVAL_MS = 200;
export const DEFAULT_LOOP_BATCH_SELECT_INTERVAL_MS = 5000;
export const MIN_LOOP_BATCH_SELECT_INTERVAL_MS = 1000;

export function normalizeBatchSelectIntervalMs(value) {
    if (value === '') {
        return DEFAULT_BATCH_SELECT_INTERVAL_MS;
    }

    const parsedValue = Number(value);
    if (!Number.isFinite(parsedValue)) {
        return DEFAULT_BATCH_SELECT_INTERVAL_MS;
    }

    return Math.max(MIN_BATCH_SELECT_INTERVAL_MS, Math.floor(parsedValue));
}

export function normalizeLoopBatchSelectIntervalMs(value) {
    if (value === '') {
        return DEFAULT_LOOP_BATCH_SELECT_INTERVAL_MS;
    }

    const parsedValue = Number(value);
    if (!Number.isFinite(parsedValue)) {
        return DEFAULT_LOOP_BATCH_SELECT_INTERVAL_MS;
    }

    return Math.max(MIN_LOOP_BATCH_SELECT_INTERVAL_MS, Math.floor(parsedValue));
}
