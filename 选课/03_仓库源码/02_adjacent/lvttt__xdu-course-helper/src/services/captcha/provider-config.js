export const CAPTCHA_PROVIDER_SCHEMA_VERSION = 2;
export const CAPTCHA_DEFAULT_PROVIDER = 'vitphp';
export const CAPTCHA_CUSTOM_PROVIDER = 'custom';
export const CAPTCHA_PROVIDER_OPTIONS = [
    {
        name: CAPTCHA_DEFAULT_PROVIDER,
        label: '内置服务: vitphp',
        type: 'builtin',
    },
];

function asObject(value) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
        return value;
    }
    return {};
}

function normalizeProviderName(value) {
    if (typeof value !== 'string') {
        return '';
    }
    return value.trim().toLowerCase();
}

function normalizeCustomProviderKey(value, fallback = '') {
    const source = typeof value === 'string' ? value : fallback;
    return String(source || '')
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9_-]+/g, '-')
        .replace(/^-+|-+$/g, '');
}

function isBuiltInProvider(providerName) {
    const normalizedName = normalizeProviderName(providerName);
    return CAPTCHA_PROVIDER_OPTIONS.some((provider) => provider.name === normalizedName);
}

function dedupeProviderList(providerList) {
    const seen = new Set();
    const result = [];
    providerList.forEach((provider) => {
        if (!provider || seen.has(provider)) {
            return;
        }
        seen.add(provider);
        result.push(provider);
    });
    return result;
}

function normalizeCustomProvider(rawProvider, index) {
    if (!rawProvider || typeof rawProvider !== 'object') {
        return null;
    }

    const id = normalizeCustomProviderKey(
        rawProvider.id,
        rawProvider.name || `provider-${index + 1}`
    );
    if (!id) {
        return null;
    }

    const method = String(rawProvider.method || 'GET').toUpperCase() === 'POST' ? 'POST' : 'GET';
    const provider = {
        id,
        name: String(rawProvider.name || `自定义服务 ${index + 1}`).trim() || `自定义服务 ${index + 1}`,
        endpoint: String(rawProvider.endpoint || '').trim(),
        method,
        imageField: String(rawProvider.imageField || 'img').trim() || 'img',
        resultPath: String(rawProvider.resultPath || '').trim(),
        successPath: String(rawProvider.successPath || '').trim(),
        successEquals:
            rawProvider.successEquals === undefined || rawProvider.successEquals === null
                ? ''
                : String(rawProvider.successEquals),
        headers: asObject(rawProvider.headers),
    };

    if (method === 'GET') {
        provider.query = asObject(rawProvider.query);
    } else {
        provider.body = asObject(rawProvider.body);
    }

    return provider;
}

function normalizeCustomProviderList(value) {
    if (!Array.isArray(value)) {
        return [];
    }

    const seen = new Set();
    const result = [];
    value.forEach((provider, index) => {
        const normalized = normalizeCustomProvider(provider, index);
        if (!normalized || seen.has(normalized.id)) {
            return;
        }
        seen.add(normalized.id);
        result.push(normalized);
    });
    return result;
}

function isValidProviderId(providerId, customProviders) {
    if (isBuiltInProvider(providerId)) {
        return true;
    }
    if (!isCustomProviderId(providerId)) {
        return false;
    }
    return isCustomProviderConfigured(findCustomProviderById(providerId, { customProviders }));
}

function normalizeChainIds(providerIds, customProviders) {
    return dedupeProviderList(normalizeProviderList(providerIds)).filter((providerId) =>
        isValidProviderId(providerId, customProviders)
    );
}

export function createCustomProviderId(value) {
    const normalizedKey = normalizeCustomProviderKey(value);
    return normalizedKey ? `${CAPTCHA_CUSTOM_PROVIDER}:${normalizedKey}` : '';
}

export function isCustomProviderId(providerName) {
    const normalizedName = normalizeProviderName(providerName);
    return normalizedName.startsWith(`${CAPTCHA_CUSTOM_PROVIDER}:`);
}

export function getCustomProviderKey(providerName) {
    if (!isCustomProviderId(providerName)) {
        return '';
    }
    return normalizeProviderName(providerName).slice(CAPTCHA_CUSTOM_PROVIDER.length + 1);
}

export function normalizeProviderList(value) {
    if (Array.isArray(value)) {
        return value.map(normalizeProviderName).filter(Boolean);
    }
    const single = normalizeProviderName(value);
    return single ? [single] : [];
}

export function getDefaultCaptchaProviderStrategy() {
    return {
        activeProvider: CAPTCHA_DEFAULT_PROVIDER,
        customProviders: [],
        providerPriority: [CAPTCHA_DEFAULT_PROVIDER],
        fallbackProviders: [],
    };
}

export function findCustomProviderById(providerName, config = {}) {
    const customProviderKey = getCustomProviderKey(providerName);
    if (!customProviderKey) {
        return null;
    }
    const customProviders = normalizeCustomProviderList(config?.customProviders);
    return customProviders.find((provider) => provider.id === customProviderKey) || null;
}

export function isCustomProviderConfigured(customProvider) {
    return Boolean(
        customProvider &&
            typeof customProvider === 'object' &&
            String(customProvider.id || '').trim() &&
            String(customProvider.endpoint || '').trim() &&
            String(customProvider.resultPath || '').trim()
    );
}

export function isCaptchaProviderAvailable(providerName, config = {}) {
    const normalizedName = normalizeProviderName(providerName);
    if (isBuiltInProvider(normalizedName)) {
        return true;
    }
    if (isCustomProviderId(normalizedName)) {
        return isCustomProviderConfigured(findCustomProviderById(normalizedName, config));
    }
    return false;
}

export function getCaptchaProviderLabel(providerName, config = {}) {
    const normalizedName = normalizeProviderName(providerName);
    const builtinLabel = CAPTCHA_PROVIDER_OPTIONS.find((provider) => provider.name === normalizedName)?.label;
    if (builtinLabel) {
        return builtinLabel;
    }
    const customProvider = findCustomProviderById(normalizedName, config);
    return customProvider?.name || providerName;
}

export function getCaptchaProviderStatusText(
    providerName,
    { providerPriority = [], fallbackProviders = [], isAvailable = true } = {}
) {
    const normalizedName = normalizeProviderName(providerName);
    const priorityIndex = normalizeProviderList(providerPriority).indexOf(normalizedName);
    if (priorityIndex >= 0) {
        return `优先链路第 ${priorityIndex + 1} 位`;
    }

    const fallbackIndex = normalizeProviderList(fallbackProviders).indexOf(normalizedName);
    if (fallbackIndex >= 0) {
        return `备用回退第 ${fallbackIndex + 1} 位`;
    }

    return isAvailable ? '未加入链路' : '未完成配置';
}

export function normalizeStoredCaptchaProviderConfig(rawConfig) {
    const defaultStrategy = getDefaultCaptchaProviderStrategy();
    if (!rawConfig || typeof rawConfig !== 'object') {
        return {
            schemaVersion: CAPTCHA_PROVIDER_SCHEMA_VERSION,
            activeProvider: defaultStrategy.activeProvider,
            customProviders: [],
            providerPriority: [...defaultStrategy.providerPriority],
            fallbackProviders: [...defaultStrategy.fallbackProviders],
        };
    }

    const customProviders = normalizeCustomProviderList(rawConfig.customProviders);
    const providerPriority = normalizeChainIds(rawConfig.providerPriority || rawConfig.providers, customProviders);
    const fallbackProviders = normalizeChainIds(rawConfig.fallbackProviders, customProviders).filter(
        (providerId) => !providerPriority.includes(providerId)
    );
    const normalizedActiveProvider = normalizeChainIds([rawConfig.activeProvider], customProviders)[0] || '';
    const defaultPriority = providerPriority.length
        ? providerPriority
        : normalizedActiveProvider
          ? [normalizedActiveProvider]
          : [CAPTCHA_DEFAULT_PROVIDER];
    const activeProvider = normalizedActiveProvider || defaultPriority[0];

    return {
        schemaVersion: CAPTCHA_PROVIDER_SCHEMA_VERSION,
        activeProvider,
        customProviders,
        providerPriority: defaultPriority,
        fallbackProviders,
    };
}

export function buildCaptchaProviderStorageConfig({
    activeProvider = CAPTCHA_DEFAULT_PROVIDER,
    customProviders = [],
    providerPriority = null,
    fallbackProviders = null,
}) {
    const normalizedCustomProviders = normalizeCustomProviderList(customProviders);
    const normalizedProviderPriority = normalizeChainIds(providerPriority, normalizedCustomProviders);
    const normalizedFallbackProviders = normalizeChainIds(
        fallbackProviders,
        normalizedCustomProviders
    ).filter((providerId) => !normalizedProviderPriority.includes(providerId));
    const normalizedActiveProvider =
        normalizeChainIds([activeProvider], normalizedCustomProviders)[0] ||
        normalizedProviderPriority[0] ||
        CAPTCHA_DEFAULT_PROVIDER;

    return {
        schemaVersion: CAPTCHA_PROVIDER_SCHEMA_VERSION,
        activeProvider: normalizedActiveProvider,
        customProviders: normalizedCustomProviders,
        providerPriority: normalizedProviderPriority.length
            ? normalizedProviderPriority
            : [normalizedActiveProvider],
        fallbackProviders: normalizedFallbackProviders,
    };
}

export function sanitizeCaptchaProviderConfigForDiagnostics(config) {
    const normalizedConfig = normalizeStoredCaptchaProviderConfig(config);

    return {
        ...normalizedConfig,
        customProviders: normalizedConfig.customProviders.map((customProvider) => ({
            id: customProvider.id,
            name: customProvider.name || '',
            endpoint: customProvider.endpoint || '',
            method: customProvider.method || 'GET',
            imageField: customProvider.imageField || 'img',
            resultPath: customProvider.resultPath || '',
            successPath: customProvider.successPath || '',
            successEquals: customProvider.successEquals || '',
            hasHeaders: Boolean(customProvider.headers && Object.keys(customProvider.headers).length > 0),
            hasQuery: Boolean(customProvider.query && Object.keys(customProvider.query).length > 0),
            hasBody: Boolean(customProvider.body && Object.keys(customProvider.body).length > 0),
        })),
    };
}
