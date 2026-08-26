import { sanitizeCaptchaProviderConfigForDiagnostics } from '../../services/captcha/provider-config';
import { getStorageValue } from '../../shared/chrome-storage';
import { DEFAULT_EXT_CONFIG } from '../../shared/config-defaults';
import { EXTENSION_STORAGE_KEYS, PAGE_STORAGE_KEYS } from '../../shared/storage-keys';

async function getPageStorageSnapshot(tabId) {
    const [injectedResult] = await chrome.scripting.executeScript({
        target: { tabId },
        world: 'MAIN',
        func: (pageStorageKeys, extConfigFallback) => {
            const helper = window.xdu_course_helper;
            const safeRead = (key) => {
                if (!helper || typeof helper.getLocalStorage !== 'function') {
                    return null;
                }
                return helper.getLocalStorage(key);
            };

            const extConfig = safeRead(pageStorageKeys.EXT_CONFIG) || extConfigFallback;
            const loginInfo = safeRead(pageStorageKeys.LOGIN_INFO);
            const courseCollection = safeRead(pageStorageKeys.COURSE_COLLECTION);
            const loginName = loginInfo?.loginName;
            const loginNameMasked =
                typeof loginName === 'string'
                    ? loginName.length <= 2
                        ? `${loginName[0]}*`
                        : `${loginName.slice(0, 2)}***${loginName.slice(-1)}`
                    : null;

            return {
                extConfig,
                hasLoginInfo: Boolean(loginInfo?.loginName && loginInfo?.loginPwd),
                loginNameMasked,
                hasLcxxMap: Boolean(safeRead(pageStorageKeys.LCXX_MAP)),
                hasXsMap: Boolean(safeRead(pageStorageKeys.XS_MAP)),
                courseCollectionCount: Array.isArray(courseCollection)
                    ? courseCollection.length
                    : 0,
            };
        },
        args: [PAGE_STORAGE_KEYS, DEFAULT_EXT_CONFIG],
    });

    return injectedResult?.result || null;
}

async function checkCustomProviderPermissions(captchaProviderConfig) {
    const customProviders = Array.isArray(captchaProviderConfig?.customProviders)
        ? captchaProviderConfig.customProviders
        : [];

    const permissionResults = await Promise.all(
        customProviders.map(async (provider) => {
            const endpoint = provider?.endpoint;
            if (!endpoint || typeof endpoint !== 'string') {
                return {
                    id: provider?.id || '',
                    name: provider?.name || provider?.id || '',
                    originPattern: null,
                    granted: null,
                };
            }

            try {
                const endpointUrl = new URL(endpoint);
                const originPattern = `${endpointUrl.origin}/*`;
                const granted = await new Promise((resolve) => {
                    chrome.permissions.contains({ origins: [originPattern] }, (result) => {
                        resolve(Boolean(result));
                    });
                });
                return {
                    id: provider.id || '',
                    name: provider.name || provider.id || '',
                    originPattern,
                    granted,
                };
            } catch {
                return {
                    id: provider?.id || '',
                    name: provider?.name || provider?.id || '',
                    originPattern: null,
                    granted: false,
                };
            }
        })
    );

    return permissionResults;
}

export async function handleGetDiagnostics(tabId) {
    const manifest = chrome.runtime.getManifest();
    const rawCaptchaProviderConfig = await getStorageValue(
        EXTENSION_STORAGE_KEYS.CAPTCHA_PROVIDER_CONFIG
    ).catch(() => null);
    const captchaProviderConfig =
        sanitizeCaptchaProviderConfigForDiagnostics(rawCaptchaProviderConfig);
    const pageStorage = await getPageStorageSnapshot(tabId).catch(() => null);
    const customProviderPermissions = await checkCustomProviderPermissions(captchaProviderConfig);

    return {
        generatedAt: new Date().toISOString(),
        extension: {
            name: manifest.name,
            version: manifest.version,
            manifestVersion: manifest.manifest_version,
        },
        storage: {
            chromeLocal: {
                captchaProviderConfig,
            },
            pageLocal: pageStorage || null,
        },
        permissions: {
            customProviderPermissions,
        },
    };
}
