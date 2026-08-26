import { installXhrHook } from '../hooks/xhr';
import { claimGuard } from '../runtime/guard';
import mockPublicInfo from '../data/mock-public-info.json';

// 选课登录页 URL
const xk_index_url = 'https://yjsxk.xidian.edu.cn/yjsxkapp/sys/xsxkapp/index.html';

// 清空cookies,并重重定向到登录页
function clearCookiesAndRedirect() {
    document.cookie.split(';').forEach(function (c) {
        document.cookie = c
            .replace(/^ +/, '')
            .replace(/=.*/, '=;expires=' + new Date().toUTCString() + ';path=/');
    });
    window.location.href = xk_index_url;
}

// localStorage 封装
function setLocalStorage(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
        console.error('Error setting localStorage:', e);
    }
}

function getLocalStorage(key) {
    try {
        const value = localStorage.getItem(key);
        return value ? JSON.parse(value) : null;
    } catch (e) {
        console.error('Error getting localStorage:', e);
        return null;
    }
}

const helper = window.xdu_course_helper || {};
Object.assign(helper, {
    clearCookiesAndRedirect,
    setLocalStorage,
    getLocalStorage,
});
window.xdu_course_helper = helper;

if (claimGuard('content:early-hook:bootstrap')) {
    installXhrHook({
        getLocalStorage,
        setLocalStorage,
        clearCookiesAndRedirect,
        mockPublicInfo,
    });
}
