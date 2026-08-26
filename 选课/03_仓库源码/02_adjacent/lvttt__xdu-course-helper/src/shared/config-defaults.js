import {
    DEFAULT_BATCH_SELECT_INTERVAL_MS,
    DEFAULT_LOOP_BATCH_SELECT_INTERVAL_MS,
} from './ext-config';

export const DEFAULT_EXT_CONFIG = {
    enableJumpXK: false,
    pageSize: 30,
    rememberMe: false,
    redirectOnError: false,
    enablePageSizeChange: false,
    batchSelectIntervalMs: DEFAULT_BATCH_SELECT_INTERVAL_MS,
    loopBatchSelectIntervalMs: DEFAULT_LOOP_BATCH_SELECT_INTERVAL_MS,
};
