<template>
    <div class="bg-white flex flex-col font-sans text-gray-800">
        <template v-if="isSupportedSite">
            <header
                class="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between sticky top-0 z-10"
            >
                <div class="flex items-center gap-2">
                    <h1 class="text-[14px] font-bold text-gray-700">XDU 选课助手</h1>
                </div>
            </header>

            <div class="flex-1 overflow-y-auto px-4 py-2">
                <div class="mb-2">
                    <SettingItem
                        title="强制进入选课系统"
                        description="跳过时间限制直接进入选课系统"
                    >
                        <template #action>
                            <ChromeSwitch v-model="extConfig.enableJumpXK" />
                        </template>
                        <template #warning v-if="extConfig.enableJumpXK">
                            <div
                                class="bg-red-50 px-2 py-1.5 rounded text-[11px] text-red-600 flex items-start gap-1"
                            >
                                <span class="mt-[1px]">⚠️</span>
                                <span>正常选课时间不建议开启。</span>
                            </div>
                        </template>
                        <template #default v-if="extConfig.enableJumpXK">
                            <ChromeButton
                                block
                                variant="primary"
                                :disabled="isPending"
                                @click="handleForceEnter"
                            >
                                {{ isPending ? '正在连接...' : '🚀 立即进入选课系统' }}
                            </ChromeButton>
                        </template>
                    </SettingItem>

                    <SettingItem
                        title="出错时自动重定向"
                        description="NullPointer时自动清除Cookie并重定向到登录页"
                    >
                        <template #action>
                            <ChromeSwitch v-model="extConfig.redirectOnError" />
                        </template>
                    </SettingItem>

                    <SettingItem title="修改每页条数" description="修改选课列表每页显示的课程条数">
                        <template #action>
                            <ChromeSwitch v-model="extConfig.enablePageSizeChange" />
                        </template>
                        <template #warning v-if="extConfig.enablePageSizeChange">
                            <div
                                class="bg-yellow-50 px-2 py-1.5 rounded text-[11px] text-yellow-700 flex items-start gap-1"
                            >
                                <span class="mt-[1px]">⚠️</span>
                                <span>过大可能导致页面卡顿，建议不超过100。</span>
                            </div>
                        </template>
                        <template #default v-if="extConfig.enablePageSizeChange">
                            <input
                                type="number"
                                v-model.number="extConfig.pageSize"
                                class="w-full px-2 py-1.5 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                                min="10"
                                max="100"
                                placeholder="请输入条数"
                            />
                        </template>
                    </SettingItem>

                    <SettingItem
                        title="批量选课请求间隔"
                        description="课程收藏批量选课时，两次请求之间的等待时间"
                    >
                        <template #warning>
                            <div
                                class="bg-yellow-50 px-2 py-1.5 rounded text-[11px] text-yellow-700 flex items-start gap-1"
                            >
                                <span class="mt-[1px]">⚠️</span>
                                <span>单位毫秒，最小 {{ MIN_BATCH_SELECT_INTERVAL_MS }}。</span>
                            </div>
                        </template>
                        <template #default>
                            <input
                                type="number"
                                v-model.number="extConfig.batchSelectIntervalMs"
                                class="w-full px-2 py-1.5 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                                :min="MIN_BATCH_SELECT_INTERVAL_MS"
                                step="100"
                                placeholder="请输入请求间隔"
                                @blur="normalizeBatchSelectIntervalInput"
                                @change="normalizeBatchSelectIntervalInput"
                            />
                        </template>
                    </SettingItem>

                    <SettingItem
                        title="循环批量选课间隔"
                        description="课程收藏循环批量选课时，两轮之间的等待时间"
                    >
                        <template #warning>
                            <div
                                class="bg-yellow-50 px-2 py-1.5 rounded text-[11px] text-yellow-700 flex items-start gap-1"
                            >
                                <span class="mt-[1px]">⚠️</span>
                                <span>单位毫秒，最小 {{ MIN_LOOP_BATCH_SELECT_INTERVAL_MS }}。</span>
                            </div>
                        </template>
                        <template #default>
                            <input
                                type="number"
                                v-model.number="extConfig.loopBatchSelectIntervalMs"
                                class="w-full px-2 py-1.5 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                                :min="MIN_LOOP_BATCH_SELECT_INTERVAL_MS"
                                step="500"
                                placeholder="请输入循环间隔"
                                @blur="normalizeLoopBatchSelectIntervalInput"
                                @change="normalizeLoopBatchSelectIntervalInput"
                            />
                        </template>
                    </SettingItem>

                    <SettingItem
                        title="记住账号密码"
                        description="只保存加密后的密码,不建议在公共电脑使用"
                    >
                        <template #action>
                            <ChromeSwitch v-model="extConfig.rememberMe" />
                        </template>
                        <template v-if="extConfig.rememberMe" #default>
                            <div
                                class="bg-gray-50 border border-gray-200 rounded-md p-3 flex flex-col gap-2"
                            >
                                <h3 class="text-[12px] font-bold text-gray-700 mb-1">系统登录</h3>
                                <div class="rounded-md border border-gray-200 bg-white overflow-hidden">
                                    <button
                                        type="button"
                                        class="w-full px-3 py-2 flex items-center justify-between text-left bg-gray-50 hover:bg-gray-100 transition-colors"
                                        @click="isCaptchaProviderPanelExpanded = !isCaptchaProviderPanelExpanded"
                                    >
                                        <div>
                                            <p class="text-[12px] font-semibold text-gray-700">
                                                验证码识别服务
                                            </p>
                                            <p class="text-[11px] text-gray-500 mt-0.5">
                                                默认收起，可展开配置多个自定义服务
                                            </p>
                                        </div>
                                        <span class="text-[11px] text-blue-600">
                                            {{ isCaptchaProviderPanelExpanded ? '收起' : '展开' }}
                                        </span>
                                    </button>

                                    <div v-if="isCaptchaProviderPanelExpanded" class="p-3 border-t border-gray-200">
                                        <CaptchaProviderPanel
                                            :bridge="bridge"
                                            :default-test-image-url="vcodeUrl"
                                        />
                                    </div>
                                </div>

                                <ChromeButton
                                    block
                                    variant="secondary"
                                    @click="handleGetVcodeToken"
                                >
                                    📄 获取验证码
                                </ChromeButton>

                                <template v-if="vcodeToken">
                                    <div class="flex items-center gap-2 mt-1">
                                        <img
                                            :src="vcodeUrl"
                                            alt="验证码"
                                            class="h-8 border border-gray-300 rounded bg-white shrink-0 cursor-pointer"
                                            @click="handleGetVcodeToken"
                                        />
                                        <input
                                            type="text"
                                            placeholder="输入验证码"
                                            v-model="vcodeText"
                                            @keyup.enter="handleLogin"
                                            class="flex-1 w-0 px-2 py-1.5 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                                        />
                                    </div>

                                    <div class="flex gap-2 mt-1">
                                        <ChromeButton block variant="primary" @click="handleLogin"
                                            >登录</ChromeButton
                                        >
                                        <ChromeButton
                                            block
                                            variant="primary"
                                            @click="handleAutoLogin"
                                            >自动识别登录</ChromeButton
                                        >
                                    </div>
                                </template>

                                <div
                                    v-if="loginResponse"
                                    class="mt-2 p-2 rounded text-[11px] break-all"
                                    :class="getLoginResponseClass(loginResponse)"
                                >
                                    <strong>响应:</strong> {{ loginResponse.msg }}
                                </div>

                                <ChromeButton
                                    block
                                    variant="secondary"
                                    class="mt-1"
                                    @click="handleClearSavedLogin"
                                >
                                    清除已记住账号
                                </ChromeButton>
                            </div>
                        </template>
                    </SettingItem>
                </div>

                <div class="mt-2 pt-4 border-t border-gray-200">
                    <p class="text-[11px] text-gray-500 mb-2">遇到白屏或系统异常(Null Pointer)？</p>
                    <ChromeButton block variant="danger" @click="handleClearCookies">
                        🧹 清理Cookie并重新登录
                    </ChromeButton>
                    <ChromeButton
                        block
                        variant="secondary"
                        class="mt-2"
                        :disabled="diagnosticsExporting"
                        @click="handleExportDiagnostics"
                    >
                        {{ diagnosticsExporting ? '导出中...' : '导出诊断信息' }}
                    </ChromeButton>
                    <p
                        v-if="diagnosticsNotice"
                        class="mt-2 text-[11px]"
                        :class="
                            diagnosticsNoticeType === 'error' ? 'text-red-600' : 'text-gray-600'
                        "
                    >
                        {{ diagnosticsNotice }}
                    </p>
                </div>
            </div>

            <footer
                class="p-3 bg-gray-50 border-t border-gray-200 text-center flex justify-between items-center text-[11px] text-gray-500"
            >
                <span>© 2026 XDU Helper</span>
                <a
                    href="https://github.com/lvttt/xdu-course-helper"
                    target="_blank"
                    class="text-blue-600 hover:underline"
                    >GitHub</a
                >
            </footer>
        </template>
        <template v-else>
            <div class="p-4 text-center text-gray-600">
                <h2 class="text-lg font-bold mb-2">不支持的页面</h2>
                <p>请在西电选课系统页面打开插件设置。</p>
            </div>
        </template>
    </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import ChromeSwitch from './ui/ChromeSwitch.vue';
import SettingItem from './ui/SettingItem.vue';
import ChromeButton from './ui/ChromeButton.vue';
import CaptchaProviderPanel from './ui/CaptchaProviderPanel.vue';
import {
    MESSAGE_ACTIONS,
    TASK_TYPES,
    ERROR_CODES,
    createRequestId,
    createErrorResponse,
} from './shared/contract';
import { logDebug, logError } from './shared/logger';
import { DEFAULT_EXT_CONFIG } from './shared/config-defaults';
import {
    MIN_BATCH_SELECT_INTERVAL_MS,
    MIN_LOOP_BATCH_SELECT_INTERVAL_MS,
    normalizeBatchSelectIntervalMs,
    normalizeLoopBatchSelectIntervalMs,
} from './shared/ext-config';
import {
    createMissingSavedLoginResponse,
    getLoginResponseClass,
} from './shared/login-feedback';
import { isSupportedCourseUrl } from './shared/site-support';

const isSupportedSite = ref(false);
const checkUrl = async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    isSupportedSite.value = isSupportedCourseUrl(tab?.url);
};

const extConfig = ref({ ...DEFAULT_EXT_CONFIG });

const diagnosticsExporting = ref(false);
const diagnosticsNotice = ref('');
const diagnosticsNoticeType = ref('info');
const isCaptchaProviderPanelExpanded = ref(false);

const setDiagnosticsNotice = (message, type = 'info') => {
    diagnosticsNoticeType.value = type;
    diagnosticsNotice.value = message;
};

const normalizeBatchSelectIntervalInput = () => {
    extConfig.value.batchSelectIntervalMs = normalizeBatchSelectIntervalMs(
        extConfig.value.batchSelectIntervalMs
    );
};

const normalizeLoopBatchSelectIntervalInput = () => {
    extConfig.value.loopBatchSelectIntervalMs = normalizeLoopBatchSelectIntervalMs(
        extConfig.value.loopBatchSelectIntervalMs
    );
};

const downloadJsonFile = (filename, payload) => {
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: 'application/json;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
};

const normalizeBridgeResponse = (rawResponse, requestId) => {
    if (rawResponse?.ok === true || rawResponse?.ok === false) {
        return rawResponse;
    }
    if (rawResponse?.success === true) {
        return {
            ok: true,
            requestId: rawResponse.requestId || requestId,
            data: rawResponse.data ?? null,
            error: null,
        };
    }
    if (rawResponse?.success === false) {
        return createErrorResponse({
            requestId: rawResponse.requestId || requestId,
            code: rawResponse.error?.code || ERROR_CODES.TASK_EXECUTION_FAILED,
            message: rawResponse.error?.message || rawResponse.error || '任务执行失败',
        });
    }
    return createErrorResponse({
        requestId,
        code: ERROR_CODES.BAD_RESPONSE_SHAPE,
        message: '后台响应格式异常',
    });
};

const syncPageConfig = async () => {
    if (!isSupportedSite.value) {
        return;
    }

    const configResponse = await bridge.sendToMain(TASK_TYPES.GET_CONFIG);
    const savedConfig = configResponse.ok ? configResponse.data : null;
    if (savedConfig) {
        extConfig.value = {
            ...extConfig.value,
            ...savedConfig,
            batchSelectIntervalMs: normalizeBatchSelectIntervalMs(savedConfig.batchSelectIntervalMs),
            loopBatchSelectIntervalMs: normalizeLoopBatchSelectIntervalMs(
                savedConfig.loopBatchSelectIntervalMs
            ),
        };
    }
};

const bridge = {
    async sendToMain(taskType, data = {}) {
        const requestId = createRequestId();
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!tab?.id) {
                return createErrorResponse({
                    requestId,
                    code: ERROR_CODES.TAB_NOT_FOUND,
                    message: '无法获取当前标签页',
                });
            }

            const rawResponse = await chrome.runtime.sendMessage({
                action: MESSAGE_ACTIONS.CALL_MAIN_FUNCTION,
                requestId,
                tabId: tab.id,
                payload: { taskType, data },
            });
            const response = normalizeBridgeResponse(rawResponse, requestId);

            logDebug('panel-bridge', 'Message finished', {
                requestId,
                taskType,
                ok: response.ok,
            });
            return response;
        } catch (err) {
            logError('panel-bridge', 'Message failed', {
                requestId,
                taskType,
                message: err?.message,
            });
            return createErrorResponse({
                requestId,
                code: ERROR_CODES.MESSAGE_SEND_FAILED,
                message: err?.message || '通信失败',
            });
        }
    },
};

const isPending = ref(false);

const handleForceEnter = async () => {
    isPending.value = true;
    const response = await bridge.sendToMain(TASK_TYPES.FORCE_ENTER);
    if (!response.ok) {
        logError('panel', 'FORCE_ENTER failed', {
            requestId: response.requestId,
            code: response.error?.code,
            message: response.error?.message,
        });
    }
    isPending.value = false;
};

const handleClearCookies = () => {
    bridge.sendToMain(TASK_TYPES.CLEAR_COOKIES).then((response) => {
        if (!response.ok) {
            logError('panel', 'CLEAR_COOKIES failed', {
                requestId: response.requestId,
                code: response.error?.code,
                message: response.error?.message,
            });
        }
    });
};

const handleClearSavedLogin = async () => {
    const response = await bridge.sendToMain(TASK_TYPES.CLEAR_SAVED_LOGIN);
    loginResponse.value = {
        type: response.ok ? 'info' : 'error',
        msg: response.ok ? '已清除记住账号信息' : response.error?.message || '清除记住账号失败',
    };
};

const handleExportDiagnostics = async () => {
    diagnosticsExporting.value = true;
    setDiagnosticsNotice('', 'info');
    try {
        const response = await bridge.sendToMain(TASK_TYPES.GET_DIAGNOSTICS);
        if (!response.ok) {
            throw new Error(response.error?.message || '获取诊断信息失败');
        }
        const diagnosticsPayload = {
            ...response.data,
            exportedAt: new Date().toISOString(),
        };
        const fileName = `xdu-helper-diagnostics-${new Date().toISOString().slice(0, 10)}.json`;
        downloadJsonFile(fileName, diagnosticsPayload);
        setDiagnosticsNotice('诊断信息已导出。');
    } catch (error) {
        setDiagnosticsNotice(error?.message || '导出诊断信息失败', 'error');
        logError('panel', 'GET_DIAGNOSTICS failed', {
            message: error?.message,
        });
    } finally {
        diagnosticsExporting.value = false;
    }
};

const vcodeToken = ref('');
const vcodeUrl = computed(() => {
    return vcodeToken.value
        ? `https://yjsxk.xidian.edu.cn/yjsxkapp/sys/xsxkapp/login/vcode/image.do?vtoken=${vcodeToken.value}`
        : '';
});
const handleGetVcodeToken = async () => {
    const response = await bridge.sendToMain(TASK_TYPES.GET_VCODE_TOKEN);
    if (response.ok && response.data) {
        vcodeToken.value = response.data;
        return true;
    }
    logError('panel', 'GET_VCODE_TOKEN failed', {
        requestId: response.requestId,
        code: response.error?.code,
        message: response.error?.message,
    });
    return false;
};
const handleCaptchaRecognize = async () => {
    const response = await bridge.sendToMain(TASK_TYPES.CAPTCHA_RECOGNIZE, {
        imageUrl: vcodeUrl.value,
    });
    if (response.ok && response.data?.code === '1' && response.data?.data?.captcha) {
        return response.data.data.captcha;
    }
    logError('panel', 'CAPTCHA_RECOGNIZE failed', {
        requestId: response.requestId,
        code: response.error?.code,
        message: response.error?.message,
    });
    return null;
};

const vcodeText = ref('');
const loginResponse = ref(null);
const ensureSavedLoginExists = async () => {
    const response = await bridge.sendToMain(TASK_TYPES.GET_SAVED_LOGIN_STATUS);
    if (response.ok && response.data?.hasSavedLogin) {
        return true;
    }

    loginResponse.value = createMissingSavedLoginResponse();
    return false;
};

const handleLoginResponse = (response) => {
    console.log('登录响应:', response);
    loginResponse.value = {
        type: response?.code === '1' ? 'info' : 'error',
        msg: response?.msg || '登录失败',
    };

    if (response && response.code === '3') {
        // 验证码不正确
        handleGetVcodeToken();
        return;
    }

    setTimeout(() => {
        loginResponse.value = null;
        vcodeToken.value = '';
        vcodeText.value = '';
    }, 10000);
};
const handleLogin = async () => {
    if (!vcodeToken.value || !vcodeText.value) {
        return;
    }
    const hasSavedLogin = await ensureSavedLoginExists();
    if (!hasSavedLogin) {
        return;
    }
    const response = await bridge.sendToMain(TASK_TYPES.LOGIN_WITH_VCODE, {
        vcodeToken: vcodeToken.value,
        vcode: vcodeText.value,
    });
    handleLoginResponse(response.ok ? response.data : { code: '0', msg: response.error?.message });
};
const handleAutoLogin = async () => {
    const hasSavedLogin = await ensureSavedLoginExists();
    if (!hasSavedLogin) {
        return;
    }
    const getVcodeTokenRes = await handleGetVcodeToken();
    if (!getVcodeTokenRes) {
        console.error('获取验证码Token失败,无法进行自动登录');
        return;
    }
    const vcode = await handleCaptchaRecognize();
    if (!vcode) {
        console.error('验证码识别失败，无法进行自动登录');
        return;
    }
    const response = await bridge.sendToMain(TASK_TYPES.LOGIN_WITH_VCODE, {
        vcodeToken: vcodeToken.value,
        vcode: vcode,
    });
    handleLoginResponse(response.ok ? response.data : { code: '0', msg: response.error?.message });
};

onMounted(async () => {
    watch(
        extConfig,
        (newConfig) => {
            if (!isSupportedSite.value) {
                return;
            }
            const normalizedConfig = {
                ...newConfig,
                batchSelectIntervalMs: normalizeBatchSelectIntervalMs(
                    newConfig.batchSelectIntervalMs
                ),
                loopBatchSelectIntervalMs: normalizeLoopBatchSelectIntervalMs(
                    newConfig.loopBatchSelectIntervalMs
                ),
            };

            bridge.sendToMain(TASK_TYPES.UPDATE_CONFIG, normalizedConfig).then((response) => {
                if (!response.ok) {
                    logError('panel', 'UPDATE_CONFIG failed', {
                        requestId: response.requestId,
                        code: response.error?.code,
                        message: response.error?.message,
                    });
                }
            });
        },
        { deep: true }
    );

    watch(
        () => extConfig.value.pageSize,
        (newPageSize) => {
            if (!isSupportedSite.value) {
                return;
            }
            bridge.sendToMain(TASK_TYPES.UPDATE_PAGE_SIZE, newPageSize).then((response) => {
                if (!response.ok) {
                    logError('panel', 'UPDATE_PAGE_SIZE failed', {
                        requestId: response.requestId,
                        code: response.error?.code,
                        message: response.error?.message,
                    });
                }
            });
        }
    );

    watch(
        () => extConfig.value.rememberMe,
        (newRememberMe) => {
            if (!newRememberMe) {
                vcodeToken.value = '';
                vcodeText.value = '';
                loginResponse.value = null;
            }
        }
    );

    const refreshPanelState = async () => {
        await checkUrl();
        await syncPageConfig();
    };

    await refreshPanelState();
    // 监听 Tab 切换，实时更新 App 内的状态
    chrome.tabs.onActivated.addListener(refreshPanelState);
    chrome.tabs.onUpdated.addListener(refreshPanelState);
});

</script>
