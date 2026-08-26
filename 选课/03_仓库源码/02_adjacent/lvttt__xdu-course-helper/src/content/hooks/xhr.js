import { claimGuard } from '../runtime/guard';
import { PAGE_STORAGE_KEYS } from '../../shared/storage-keys';

export function installXhrHook({
    getLocalStorage,
    setLocalStorage,
    clearCookiesAndRedirect,
    mockPublicInfo,
}) {
    if (!claimGuard('content:hook:xhr')) {
        return;
    }

    const OriginalXHR = window.XMLHttpRequest;

    function HookedXHR() {
        const xhr = new OriginalXHR();
        const originalOpen = xhr.open;
        const originalXHRSend = xhr.send;

        xhr.open = function (method, url) {
            this.__url = url;
            this.__method = method;
            return originalOpen.apply(this, arguments);
        };

        xhr.send = function (data) {
            if (this.__url) {
                const extConfig = getLocalStorage(PAGE_STORAGE_KEYS.EXT_CONFIG) || {};
                if (this.__url.includes('check/login.do')) {
                    if (data && extConfig.rememberMe) {
                        const params = new URLSearchParams(data);
                        const loginInfo = {
                            loginName: params.get('loginName'),
                            loginPwd: params.get('loginPwd'),
                        };
                        setLocalStorage(PAGE_STORAGE_KEYS.LOGIN_INFO, loginInfo);
                    }
                }
            }

            return originalXHRSend.apply(this, arguments);
        };

        xhr.addEventListener('readystatechange', function () {
            if (xhr.readyState === 4 && xhr.status === 200) {
                if (!this.__url) {
                    return;
                }

                const extConfig = getLocalStorage(PAGE_STORAGE_KEYS.EXT_CONFIG) || {};
                let data = xhr.responseText;
                let jsonData = false;

                if (this.__url.includes('.do')) {
                    try {
                        data = JSON.parse(xhr.responseText);
                        jsonData = true;
                    } catch {
                        if (extConfig.redirectOnError) {
                            clearCookiesAndRedirect();
                        }
                    }

                    if (data.msg && data.msg === 'NullPointer') {
                        if (extConfig.redirectOnError) {
                            clearCookiesAndRedirect();
                        }
                        console.error(
                            'Received NullPointer error from server, please redirecting to login page.'
                        );
                    }
                }

                if (this.__url.includes('loadPublicInfo_course.do')) {
                    if (data.loginUserId != '') {
                        if (extConfig.enableJumpXK) {
                            const lcxxMap = getLocalStorage(PAGE_STORAGE_KEYS.LCXX_MAP);
                            const xsMap = getLocalStorage(PAGE_STORAGE_KEYS.XS_MAP);
                            if (lcxxMap) {
                                mockPublicInfo.lcxxMap = lcxxMap;
                            }
                            if (xsMap) {
                                mockPublicInfo.xsMap = xsMap;
                            }
                            data = {
                                ...mockPublicInfo,
                                ...data,
                                msg: null,
                                tip: null,
                            };
                        }

                        if (extConfig.enablePageSizeChange && extConfig.pageSize) {
                            data.xtcsMap.xkgl_xsxkmymrxsjls = extConfig.pageSize.toString();
                        }
                    }
                    console.log('Mocked loadPublicInfo_course.do response:', data);
                } else if (this.__url.includes('loadPublicInfo_index.do')) {
                    if (data.lcxx) {
                        setLocalStorage(PAGE_STORAGE_KEYS.LCXX_MAP, data.lcxx);
                        console.log('已缓存 lcxxMap 数据到 localStorage');
                    }
                } else if (this.__url.includes('loadStdInfo.do')) {
                    if (data.xs) {
                        setLocalStorage(PAGE_STORAGE_KEYS.XS_MAP, data.xs);
                        console.log('已缓存 xsMap 数据到 localStorage');
                    }
                } else if (this.__url.includes('check/login.do')) {
                    if (data.code === '1') {
                        console.log('登录成功，已保存账号密码到 localStorage');
                    } else {
                        setLocalStorage(PAGE_STORAGE_KEYS.LOGIN_INFO, null);
                    }
                }

                Object.defineProperty(xhr, 'responseText', {
                    get: () => (jsonData ? JSON.stringify(data) : data),
                });
            }
        });

        return xhr;
    }

    window.XMLHttpRequest = HookedXHR;
}
