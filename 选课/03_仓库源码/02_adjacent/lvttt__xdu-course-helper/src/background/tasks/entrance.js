// background/tasks/entrance.js

// 处理进入选课系统的逻辑
export async function handleForceEnter(tabId) {
    return chrome.scripting.executeScript({
        target: { tabId },
        world: 'MAIN',
        func: () => {
            if (window.commonUtil && window.BaseUrl) {
                window.commonUtil.gotoDzPage('course', window.BaseUrl + '/sys/xsxkapp/');
            }
        },
    });
}

// 处理清除登录状态的逻辑
export async function handleClearCookies(tabId) {
    return chrome.scripting.executeScript({
        target: { tabId },
        world: 'MAIN',
        func: () => {
            window.xdu_course_helper.clearCookiesAndRedirect();
        },
    });
}
