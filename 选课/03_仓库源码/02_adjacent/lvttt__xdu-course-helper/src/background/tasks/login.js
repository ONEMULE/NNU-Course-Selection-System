// src/background/tasks/login.js
import { PAGE_STORAGE_KEYS } from '../../shared/storage-keys.js';
import { recognizeCaptchaImage } from '../../services/captcha/index.js';
import { getVcodeToken, createVcodeImageUrl } from './vcode.js';

export function hasSavedLoginCredentials(loginInfo) {
    return Boolean(loginInfo?.loginName && loginInfo?.loginPwd);
}

export function createSilentLoginResult(result) {
    return {
        ...result,
        shouldReload: false,
    };
}

export async function handleGetSavedLoginStatus(tabId) {
    return chrome.scripting
        .executeScript({
            target: { tabId },
            world: 'MAIN',
            func: (loginInfoKey) => {
                const loginInfo = window.xdu_course_helper?.getLocalStorage?.(loginInfoKey);
                return {
                    hasSavedLogin: Boolean(loginInfo?.loginName && loginInfo?.loginPwd),
                };
            },
            args: [PAGE_STORAGE_KEYS.LOGIN_INFO],
        })
        .then((results) => {
            const [{ result }] = results;
            return result;
        });
}

export async function handleLoginWithVcode(
    tabId,
    { vcodeToken, vcode, reloadOnSuccess = true } = {}
) {
    return chrome.scripting
        .executeScript({
            target: { tabId },
            world: 'MAIN',
            func: async (loginData, loginInfoKey) => {
                const loginUrl =
                    'https://yjsxk.xidian.edu.cn/yjsxkapp/sys/xsxkapp/login/check/login.do';
                const { vcodeToken, vcode, reloadOnSuccess } = loginData;
                const loginInfo = window.xdu_course_helper.getLocalStorage(loginInfoKey);
                if (!loginInfo) {
                    throw new Error('未找到登录信息，请先登录一次并勾选记住账号密码');
                }
                const payload = new URLSearchParams();
                payload.append('loginName', loginInfo.loginName);
                payload.append('loginPwd', loginInfo.loginPwd);
                payload.append('vtoken', vcodeToken);
                payload.append('verifyCode', vcode);

                try {
                    const response = await fetch(loginUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                        body: payload.toString(),
                    });

                    const result = await response.json();
                    if (result.code === '1' && reloadOnSuccess) {
                        // 登录成功，刷新页面
                        window.location.reload();
                    }

                    console.log('登录请求结果:', result);
                    return result;
                } catch (err) {
                    console.error('登录请求失败:', err);
                    if (err instanceof SyntaxError) {
                        // 登录错误次数过多,限制5分钟内禁止登录
                        return { code: '4', msg: '登录错误次数过多,限制5分钟内禁止登录' };
                    }
                    throw err;
                }
            },
            args: [{ vcodeToken, vcode, reloadOnSuccess }, PAGE_STORAGE_KEYS.LOGIN_INFO],
        })
        .then((results) => {
            const [{ result }] = results;
            return reloadOnSuccess ? result : createSilentLoginResult(result);
        });
}

export async function handleLoopBatchSelectRelogin(tabId) {
    const vcodeToken = await getVcodeToken(tabId);
    const imageUrl = createVcodeImageUrl(vcodeToken);
    const captchaResult = await recognizeCaptchaImage({ imageUrl });
    const loginResult = await handleLoginWithVcode(tabId, {
        vcodeToken,
        vcode: captchaResult.captcha,
        reloadOnSuccess: false,
    });

    return {
        ...loginResult,
        vcodeToken,
        captchaProvider: captchaResult.provider,
        failedCaptchaAttempts: captchaResult.failedAttempts || [],
    };
}

export async function handleClearSavedLogin(tabId) {
    return chrome.scripting.executeScript({
        target: { tabId },
        world: 'MAIN',
        func: (loginInfoKey) => {
            window.xdu_course_helper.setLocalStorage(loginInfoKey, null);
            return true;
        },
        args: [PAGE_STORAGE_KEYS.LOGIN_INFO],
    });
}
