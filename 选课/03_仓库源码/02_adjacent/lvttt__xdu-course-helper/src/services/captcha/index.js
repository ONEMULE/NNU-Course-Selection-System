import { ERROR_CODES, createTaskError } from '../../shared/contract.js';
import { logDebug, logError, logWarn } from '../../shared/logger.js';
import { getStorageValue } from '../../shared/chrome-storage.js';
import { EXTENSION_STORAGE_KEYS } from '../../shared/storage-keys.js';
import { recognizeWithCustomProvider } from './custom.js';
import {
    CAPTCHA_DEFAULT_PROVIDER,
    findCustomProviderById,
    isCaptchaProviderAvailable,
    isCustomProviderId,
    normalizeProviderList as normalizeProviderListFromConfig,
    normalizeStoredCaptchaProviderConfig,
} from './provider-config.js';
import { recognizeWithVitphp } from './providers/vitphp.js';

const DEFAULT_TIMEOUT_MS = 10000;

const BUILTIN_PROVIDERS = {
    vitphp: recognizeWithVitphp,
};

function normalizeCustomProviderSource(customConfig, storedConfig) {
    if (Array.isArray(customConfig)) {
        return { customProviders: customConfig };
    }
    if (customConfig && typeof customConfig === 'object') {
        if (Array.isArray(customConfig.customProviders)) {
            return { customProviders: customConfig.customProviders };
        }
        if (customConfig.id || customConfig.endpoint) {
            return { customProviders: [customConfig] };
        }
    }
    return { customProviders: storedConfig?.customProviders || [] };
}

function toProviderDescriptor(providerName, { customConfig, storedConfig, handlers }) {
    if (isCustomProviderId(providerName)) {
        const customProvider = findCustomProviderById(
            providerName,
            normalizeCustomProviderSource(customConfig, storedConfig)
        );
        if (!isCaptchaProviderAvailable(providerName, { customProviders: customProvider ? [customProvider] : [] })) {
            throw createTaskError(
                ERROR_CODES.CAPTCHA_PROVIDER_INVALID,
                `Custom captcha provider config is missing: ${providerName}`
            );
        }
        return {
            name: providerName,
            recognize: (ctx) =>
                recognizeWithCustomProvider({
                    ...ctx,
                    config: customProvider,
                }),
        };
    }

    const providerHandler = handlers[providerName];
    if (!providerHandler) {
        throw createTaskError(
            ERROR_CODES.CAPTCHA_PROVIDER_INVALID,
            `Unknown captcha provider: ${providerName}`
        );
    }

    return {
        name: providerName,
        recognize: providerHandler,
    };
}

function dedupeProviders(providerNames) {
    const seen = new Set();
    const result = [];
    providerNames.forEach((name) => {
        if (!name || seen.has(name)) {
            return;
        }
        seen.add(name);
        result.push(name);
    });
    return result;
}

export function resolveProviderChain({
    provider,
    customConfig,
    storedConfig,
    handlers = BUILTIN_PROVIDERS,
}) {
    const explicitProviders = normalizeProviderListFromConfig(provider);
    const normalizedStoredConfig = normalizeStoredCaptchaProviderConfig(storedConfig);
    const storedPriority = normalizeProviderListFromConfig(normalizedStoredConfig.providerPriority);
    const storedFallback = normalizeProviderListFromConfig(
        normalizedStoredConfig.fallbackProviders
    );
    const activeProvider = normalizedStoredConfig.activeProvider || CAPTCHA_DEFAULT_PROVIDER;

    const providerNames = explicitProviders.length
        ? [...explicitProviders]
        : storedPriority.length
          ? [...storedPriority]
          : [activeProvider];

    if (!explicitProviders.length && storedFallback.length) {
        providerNames.push(...storedFallback);
    }
    if (!providerNames.includes(CAPTCHA_DEFAULT_PROVIDER)) {
        providerNames.push(CAPTCHA_DEFAULT_PROVIDER);
    }

    const strictMode = explicitProviders.length > 0;
    const providerChain = [];

    dedupeProviders(providerNames).forEach((providerName) => {
        try {
            providerChain.push(
                toProviderDescriptor(providerName, {
                    customConfig,
                    storedConfig: normalizedStoredConfig,
                    handlers,
                })
            );
        } catch (error) {
            if (strictMode) {
                throw error;
            }
            logWarn('captcha', 'Skip unavailable provider from chain', {
                provider: providerName,
                message: error?.message,
            });
        }
    });

    if (providerChain.length === 0) {
        throw createTaskError(
            ERROR_CODES.CAPTCHA_PROVIDER_INVALID,
            'No available captcha provider in current fallback chain'
        );
    }

    return providerChain;
}

function createTimeoutController(timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    return {
        signal: controller.signal,
        dispose: () => clearTimeout(timer),
    };
}

export async function executeCaptchaProviderChain({
    imageUrl,
    providerChain,
    timeoutMs = DEFAULT_TIMEOUT_MS,
}) {
    if (!imageUrl || typeof imageUrl !== 'string') {
        throw createTaskError(
            ERROR_CODES.CAPTCHA_IMAGE_URL_REQUIRED,
            'Captcha image url is required'
        );
    }

    const timeout = Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : DEFAULT_TIMEOUT_MS;
    const attempts = [];
    const failedAttempts = [];
    const resolvedProviderChain = Array.isArray(providerChain)
        ? providerChain.map((item) => item.name)
        : [];

    for (const providerResolver of providerChain || []) {
        const startedAt = Date.now();
        const timerContext = createTimeoutController(timeout);
        try {
            const text = await providerResolver.recognize({
                imageUrl,
                signal: timerContext.signal,
            });
            const durationMs = Date.now() - startedAt;
            attempts.push({
                provider: providerResolver.name,
                status: 'success',
                durationMs,
                message: '识别成功',
                captcha: text,
            });
            logDebug('captcha', 'Captcha recognized', {
                provider: providerResolver.name,
                attempts: failedAttempts.length + 1,
            });
            return {
                provider: providerResolver.name,
                captcha: text,
                attempts,
                failedAttempts,
                resolvedProviderChain,
            };
        } catch (error) {
            const durationMs = Date.now() - startedAt;
            const message =
                error?.name === 'AbortError'
                    ? 'Captcha request timed out'
                    : error?.message || 'Captcha recognize failed';
            const failedAttempt = {
                provider: providerResolver.name,
                code: error?.code || ERROR_CODES.CAPTCHA_RECOGNIZE_FAILED,
                message,
            };
            failedAttempts.push(failedAttempt);
            attempts.push({
                provider: providerResolver.name,
                status: 'error',
                durationMs,
                message,
                code: failedAttempt.code,
            });
            logError('captcha', 'Captcha provider failed, try next provider', {
                provider: providerResolver.name,
                message,
            });
        } finally {
            timerContext.dispose();
        }
    }

    throw createTaskError(ERROR_CODES.CAPTCHA_RECOGNIZE_FAILED, 'All captcha providers failed', {
        attempts,
        failedAttempts,
        resolvedProviderChain,
    });
}

async function getStoredCaptchaProviderConfig() {
    return getStorageValue(EXTENSION_STORAGE_KEYS.CAPTCHA_PROVIDER_CONFIG).catch(() => null);
}

export async function recognizeCaptchaImage({
    imageUrl,
    provider = null,
    customConfig = null,
    timeoutMs = DEFAULT_TIMEOUT_MS,
}) {
    const storedConfig = await getStoredCaptchaProviderConfig();
    const providerChain = resolveProviderChain({
        provider,
        customConfig,
        storedConfig,
    });
    const result = await executeCaptchaProviderChain({
        imageUrl,
        providerChain,
        timeoutMs,
    });

    return {
        provider: result.provider,
        captcha: result.captcha,
        failedAttempts: result.failedAttempts,
    };
}

export async function testCaptchaProviderChain({
    imageUrl,
    provider = null,
    customConfig = null,
    timeoutMs = DEFAULT_TIMEOUT_MS,
}) {
    const storedConfig = await getStoredCaptchaProviderConfig();
    const providerChain = resolveProviderChain({
        provider,
        customConfig,
        storedConfig,
    });
    const result = await executeCaptchaProviderChain({
        imageUrl,
        providerChain,
        timeoutMs,
    });

    return {
        imageUrl,
        provider: result.provider,
        captcha: result.captcha,
        resolvedProviderChain: result.resolvedProviderChain,
        attempts: result.attempts,
    };
}
