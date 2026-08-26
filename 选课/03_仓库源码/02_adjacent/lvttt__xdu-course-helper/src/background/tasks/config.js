// src/background/tasks/config.js
import { DEFAULT_EXT_CONFIG } from '../../shared/config-defaults';
import { PAGE_STORAGE_KEYS } from '../../shared/storage-keys';
import { isSupportedCourseUrl } from '../../shared/site-support';

async function canAccessPage(tabId) {
    const tab = await chrome.tabs.get(tabId).catch(() => null);
    return isSupportedCourseUrl(tab?.url);
}

// 获取扩展配置
export async function handleGetConfig(tabId) {
    if (!(await canAccessPage(tabId))) {
        return DEFAULT_EXT_CONFIG;
    }

    return chrome.scripting
        .executeScript({
            target: { tabId },
            world: 'MAIN',
            func: (configKey) => {
                return window.xdu_course_helper.getLocalStorage(configKey);
            },
            args: [PAGE_STORAGE_KEYS.EXT_CONFIG],
        })
        .then((results) => {
            const [{ result }] = results;
            return result || DEFAULT_EXT_CONFIG;
        });
}

// 更新扩展配置
export async function handleUpdateConfig(tabId, newConfig) {
    if (!(await canAccessPage(tabId))) {
        return null;
    }

    return chrome.scripting.executeScript({
        target: { tabId },
        world: 'MAIN',
        func: (configKey, config) => {
            window.xdu_course_helper.setLocalStorage(configKey, config);
        },
        args: [PAGE_STORAGE_KEYS.EXT_CONFIG, newConfig],
    });
}

// 修改 PageSize
export async function handleUpdatePageSize(tabId, pageSize) {
    if (!(await canAccessPage(tabId))) {
        return null;
    }

    return chrome.scripting.executeScript({
        target: { tabId },
        world: 'MAIN',
        func: (size) => {
            window.WIS_XTCS.xkgl_xsxkmymrxsjls = size.toString();
        },
        args: [pageSize],
    });
}
