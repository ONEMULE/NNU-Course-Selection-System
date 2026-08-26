<template>
    <div class="bg-white border border-gray-200 shadow-sm rounded-md p-3 space-y-4">
        <div>
            <h3 class="text-sm font-semibold text-gray-800">验证码识别服务</h3>
            <p class="text-xs text-gray-500 mt-0.5">
                支持多个自定义服务，并可加入优先链路与回退链路。
            </p>
        </div>

        <div class="border border-gray-200 rounded-md bg-gray-50 p-3 space-y-3">
            <div class="flex items-center justify-between gap-2">
                <div>
                    <p class="text-[12px] font-semibold text-gray-800">自定义服务</p>
                    <p class="text-[11px] text-gray-500">每个服务都可单独加入识别链路。</p>
                </div>
                <button
                    type="button"
                    class="px-2 py-1 text-[11px] rounded border border-blue-200 text-blue-600 hover:bg-blue-50"
                    @click="handleAddCustomProvider"
                >
                    新增服务
                </button>
            </div>

            <div
                v-if="!captchaProviderForm.customProviders.length"
                class="rounded-md border border-dashed border-gray-300 bg-white px-3 py-2 text-[11px] text-gray-500"
            >
                暂无自定义服务，可按需新增。
            </div>

            <div v-else class="space-y-2">
                <div
                    v-for="provider in captchaProviderForm.customProviders"
                    :key="provider.id"
                    class="border rounded-md p-2 bg-white"
                    :class="selectedCustomProviderId === provider.id ? 'border-blue-300' : 'border-gray-200'"
                >
                    <div class="flex items-start justify-between gap-2">
                        <div class="min-w-0">
                            <p class="text-[12px] font-medium text-gray-700 truncate">
                                {{ provider.name || '未命名服务' }}
                            </p>
                            <p class="text-[11px] text-gray-500">
                                {{ getCustomProviderMetaText(provider) }}
                            </p>
                        </div>
                        <div class="flex flex-wrap gap-1 justify-end">
                            <button
                                type="button"
                                class="px-2 py-1 text-[11px] rounded border border-gray-300 text-gray-600 hover:bg-gray-100"
                                @click="selectCustomProvider(provider.id)"
                            >
                                {{ selectedCustomProviderId === provider.id ? '编辑中' : '编辑' }}
                            </button>
                            <button
                                type="button"
                                class="px-2 py-1 text-[11px] rounded border border-red-200 text-red-600 hover:bg-red-50"
                                @click="removeCustomProvider(provider.id)"
                            >
                                删除
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div v-if="currentCustomProvider" class="border border-gray-200 rounded-md bg-white p-3 space-y-2">
            <div>
                <p class="text-[12px] font-semibold text-gray-800">编辑自定义服务</p>
                <p class="text-[11px] text-gray-500">保存前会校验 JSON 格式和接口权限。</p>
            </div>
            <input
                v-model.trim="currentCustomProvider.name"
                type="text"
                placeholder="服务名称，例如：备用 OCR A"
                class="w-full px-3 py-2 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500"
            />
            <input
                v-model.trim="currentCustomProvider.endpoint"
                type="url"
                placeholder="接口地址，例如：https://example.com/ocr"
                class="w-full px-3 py-2 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500"
            />
            <div class="grid grid-cols-2 gap-2">
                <input
                    v-model.trim="currentCustomProvider.imageField"
                    type="text"
                    placeholder="图片字段名（默认 img）"
                    class="w-full px-3 py-2 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                />
                <select
                    v-model="currentCustomProvider.method"
                    class="w-full px-3 py-2 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                >
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                </select>
            </div>
            <input
                v-model.trim="currentCustomProvider.resultPath"
                type="text"
                placeholder="返回字段路径，例如：data.text"
                class="w-full px-3 py-2 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500"
            />
            <div class="grid grid-cols-2 gap-2">
                <input
                    v-model.trim="currentCustomProvider.successPath"
                    type="text"
                    placeholder="成功判断路径（可选）"
                    class="w-full px-3 py-2 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                />
                <input
                    v-model.trim="currentCustomProvider.successEquals"
                    type="text"
                    placeholder="成功值（可选）"
                    class="w-full px-3 py-2 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500"
                />
            </div>
            <textarea
                v-model.trim="currentCustomProvider.headersJson"
                rows="2"
                placeholder='请求头 JSON，例如：{"Authorization":"Bearer xxx"}'
                class="w-full px-3 py-2 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500 resize-y"
            ></textarea>
            <textarea
                v-model.trim="currentCustomProvider.payloadJson"
                rows="2"
                placeholder='额外参数 JSON，例如：{"type":"4"}'
                class="w-full px-3 py-2 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500 resize-y"
            ></textarea>
        </div>

        <div class="border border-gray-200 rounded-md bg-gray-50 p-3 space-y-2">
            <div class="flex items-start justify-between gap-2">
                <div>
                    <p class="text-[12px] font-semibold text-gray-800">回退链配置</p>
                    <p class="text-[11px] text-gray-500">排序越靠前越优先执行。</p>
                </div>
                <button
                    type="button"
                    class="text-[11px] text-blue-600 hover:underline"
                    @click="handleResetProviderStrategy"
                >
                    恢复默认
                </button>
            </div>
            <div class="text-[11px] text-gray-600 space-y-0.5">
                <p>优先链路：{{ formatChainSummary(captchaProviderForm.providerPriority) }}</p>
                <p>备用回退：{{ formatChainSummary(captchaProviderForm.fallbackProviders) }}</p>
            </div>
            <div class="space-y-2">
                <div
                    v-for="provider in providerCatalog"
                    :key="provider.name"
                    class="border border-gray-200 rounded-md p-2 bg-white"
                >
                    <div class="flex items-start justify-between gap-2">
                        <div class="min-w-0">
                            <p class="text-[12px] font-medium text-gray-700 truncate">
                                {{ provider.label }}
                            </p>
                            <p class="text-[11px] text-gray-500">
                                {{ getProviderStatusText(provider.name) }}
                            </p>
                        </div>
                        <div class="flex flex-wrap gap-1 justify-end items-center">
                            <button
                                v-if="getProviderChainType(provider.name) !== 'priority'"
                                type="button"
                                class="px-2 py-1 text-[11px] rounded border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-50"
                                :disabled="!provider.available"
                                @click="assignProviderToChain(provider.name, 'priority')"
                            >
                                设为优先
                            </button>
                            <button
                                v-if="getProviderChainType(provider.name) !== 'fallback'"
                                type="button"
                                class="px-2 py-1 text-[11px] rounded border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-50"
                                :disabled="!provider.available"
                                @click="assignProviderToChain(provider.name, 'fallback')"
                            >
                                设为回退
                            </button>
                            <button
                                v-if="getProviderChainType(provider.name)"
                                type="button"
                                class="px-2 py-1 text-[11px] rounded border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-50"
                                :disabled="!canMoveProvider(provider.name, -1)"
                                @click="moveProvider(provider.name, -1)"
                            >
                                上移
                            </button>
                            <button
                                v-if="getProviderChainType(provider.name)"
                                type="button"
                                class="px-2 py-1 text-[11px] rounded border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-50"
                                :disabled="!canMoveProvider(provider.name, 1)"
                                @click="moveProvider(provider.name, 1)"
                            >
                                下移
                            </button>
                            <button
                                v-if="getProviderChainType(provider.name)"
                                type="button"
                                class="px-2 py-1 text-[11px] rounded border border-red-200 text-red-600 hover:bg-red-50"
                                @click="removeProviderFromChain(provider.name)"
                            >
                                移出
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="border border-gray-200 rounded-md bg-gradient-to-br from-blue-50 to-white p-3 space-y-2">
            <div>
                <p class="text-[12px] font-semibold text-gray-800">验证码单次测试</p>
                <p class="text-[11px] text-gray-500">测试时会使用当前面板里的链路和自定义服务配置。</p>
            </div>
            <input
                v-model.trim="captchaTestImageUrl"
                type="url"
                placeholder="输入验证码图片 URL"
                class="w-full px-3 py-2 text-[12px] border border-gray-300 rounded focus:outline-none focus:border-blue-500"
            />
            <div class="grid grid-cols-2 gap-2">
                <ChromeButton
                    block
                    variant="secondary"
                    :disabled="!props.defaultTestImageUrl"
                    @click="fillDefaultTestImageUrl"
                >
                    使用当前验证码
                </ChromeButton>
                <ChromeButton
                    block
                    variant="primary"
                    :disabled="captchaTestRunning"
                    @click="handleRunCaptchaTest"
                >
                    {{ captchaTestRunning ? '测试中...' : '单次测试' }}
                </ChromeButton>
            </div>
            <div
                v-if="captchaTestResult"
                class="rounded border border-white/70 bg-white/80 px-3 py-2 text-[11px]"
            >
                <p>
                    {{ captchaTestResult.success ? '识别成功' : '识别失败' }}
                    <template v-if="captchaTestResult.provider">
                        ，最终命中 {{ getProviderLabel(captchaTestResult.provider) }}
                    </template>
                </p>
                <p v-if="captchaTestResult.captcha" class="text-sm font-mono text-gray-800 mt-1">
                    结果：{{ captchaTestResult.captcha }}
                </p>
                <p v-if="captchaTestResult.errorMessage" class="text-red-600 mt-1">
                    失败：{{ captchaTestResult.errorMessage }}
                </p>
                <div v-if="captchaTestResult.attempts?.length" class="mt-2 space-y-2">
                    <div
                        v-for="attempt in captchaTestResult.attempts"
                        :key="`${attempt.provider}-${attempt.status}-${attempt.durationMs}`"
                        class="border border-gray-200 rounded-md p-2 bg-white"
                    >
                        <div class="flex items-center justify-between text-[11px] gap-2">
                            <span class="font-semibold truncate">{{ getProviderLabel(attempt.provider) }}</span>
                            <span>
                                {{ attempt.status === 'success' ? '成功' : '失败' }} ·
                                {{ attempt.durationMs }}ms
                            </span>
                        </div>
                        <p class="text-[10px] text-gray-600 mt-1 break-all">
                            {{ attempt.message }}
                        </p>
                        <p v-if="attempt.captcha" class="text-[10px] text-gray-600 mt-0.5">
                            结果：{{ attempt.captcha }}
                        </p>
                    </div>
                </div>
            </div>
        </div>

        <ChromeButton
            block
            variant="primary"
            :disabled="captchaProviderSaving"
            @click="handleSaveCaptchaProvider"
        >
            {{ captchaProviderSaving ? '保存中...' : '保存识别服务配置' }}
        </ChromeButton>
        <div class="grid grid-cols-2 gap-2">
            <ChromeButton block variant="secondary" @click="handleExportCaptchaProviderConfig">
                导出识别配置
            </ChromeButton>
            <ChromeButton block variant="secondary" @click="triggerCaptchaProviderImport">
                导入识别配置
            </ChromeButton>
        </div>
        <input
            ref="captchaConfigImportInput"
            type="file"
            accept="application/json,.json"
            class="hidden"
            @change="handleImportCaptchaProviderConfig"
        />
        <p
            v-if="captchaProviderNotice"
            class="text-[11px]"
            :class="captchaProviderNoticeType === 'error' ? 'text-red-600' : 'text-gray-600'"
        >
            {{ captchaProviderNotice }}
        </p>
    </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import ChromeButton from './ChromeButton.vue';
import { getStorageValue, setStorageValue } from '../shared/chrome-storage.js';
import { EXTENSION_STORAGE_KEYS } from '../shared/storage-keys.js';
import {
    TASK_TYPES,
    ERROR_CODES,
    createErrorResponse,
    createRequestId,
} from '../shared/contract.js';
import {
    CAPTCHA_DEFAULT_PROVIDER,
    CAPTCHA_PROVIDER_OPTIONS,
    buildCaptchaProviderStorageConfig,
    createCustomProviderId,
    getCaptchaProviderLabel,
    getCaptchaProviderStatusText,
    getDefaultCaptchaProviderStrategy,
    isCaptchaProviderAvailable,
    normalizeProviderList,
    normalizeStoredCaptchaProviderConfig,
} from '../services/captcha/provider-config.js';

const props = defineProps({
    bridge: {
        type: Object,
        required: true,
    },
    defaultTestImageUrl: {
        type: String,
        default: '',
    },
});

const captchaProviderForm = ref({
    customProviders: [],
    providerPriority: [CAPTCHA_DEFAULT_PROVIDER],
    fallbackProviders: [],
});
const selectedCustomProviderId = ref('');
const captchaProviderSaving = ref(false);
const captchaProviderNotice = ref('');
const captchaProviderNoticeType = ref('info');
const captchaConfigImportInput = ref(null);
const captchaTestImageUrl = ref('');
const captchaTestRunning = ref(false);
const captchaTestResult = ref(null);

const currentCustomProvider = computed(
    () =>
        captchaProviderForm.value.customProviders.find(
            (provider) => provider.id === selectedCustomProviderId.value
        ) || null
);

const providerCatalog = computed(() => {
    const builtins = CAPTCHA_PROVIDER_OPTIONS.map((provider) => ({
        name: provider.name,
        label: provider.label,
        available: true,
    }));
    const customProviders = captchaProviderForm.value.customProviders.map((provider) => ({
        name: createCustomProviderId(provider.id),
        label: provider.name || '未命名服务',
        available: isCaptchaProviderAvailable(createCustomProviderId(provider.id), {
            customProviders: captchaProviderForm.value.customProviders,
        }),
    }));
    return [...builtins, ...customProviders];
});

const providerLabelMap = computed(() => {
    return Object.fromEntries(providerCatalog.value.map((provider) => [provider.name, provider.label]));
});

const setCaptchaProviderNotice = (message, type = 'info') => {
    captchaProviderNoticeType.value = type;
    captchaProviderNotice.value = message;
};

const createEmptyCustomProvider = () => ({
    id: `provider-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
    name: `自定义服务 ${captchaProviderForm.value.customProviders.length + 1}`,
    endpoint: '',
    method: 'GET',
    imageField: 'img',
    resultPath: 'captcha',
    successPath: '',
    successEquals: '',
    headersJson: '{}',
    payloadJson: '{}',
});

const toEditableCustomProvider = (provider, index) => ({
    id: provider.id,
    name: provider.name || `自定义服务 ${index + 1}`,
    endpoint: provider.endpoint || '',
    method: provider.method || 'GET',
    imageField: provider.imageField || 'img',
    resultPath: provider.resultPath || 'captcha',
    successPath: provider.successPath || '',
    successEquals: provider.successEquals || '',
    headersJson: JSON.stringify(provider.headers || {}, null, 2),
    payloadJson: JSON.stringify(provider.query || provider.body || {}, null, 2),
});

const normalizeChainState = (providerPriority, fallbackProviders, customProviderIds = null) => {
    const validIds = new Set([
        CAPTCHA_DEFAULT_PROVIDER,
        ...(customProviderIds
            ? [...customProviderIds]
            : captchaProviderForm.value.customProviders.map((provider) => createCustomProviderId(provider.id))),
    ]);
    const dedupedPriority = normalizeProviderList(providerPriority).filter((providerId) =>
        validIds.has(providerId)
    );
    const dedupedFallback = normalizeProviderList(fallbackProviders)
        .filter((providerId) => validIds.has(providerId))
        .filter((providerId) => !dedupedPriority.includes(providerId));

    if (!dedupedPriority.length) {
        dedupedPriority.push(getDefaultCaptchaProviderStrategy().providerPriority[0]);
    }

    return {
        providerPriority: [...new Set(dedupedPriority)],
        fallbackProviders: [...new Set(dedupedFallback)],
    };
};

const applyFormConfig = (storedConfig) => {
    const normalized = normalizeStoredCaptchaProviderConfig(storedConfig);
    const customProviders = normalized.customProviders.map((provider, index) =>
        toEditableCustomProvider(provider, index)
    );
    const customProviderIds = new Set(
        customProviders.map((provider) => createCustomProviderId(provider.id))
    );
    const normalizedChains = normalizeChainState(
        normalized.providerPriority,
        normalized.fallbackProviders,
        customProviderIds
    );

    captchaProviderForm.value.customProviders = customProviders;
    captchaProviderForm.value.providerPriority = normalizedChains.providerPriority;
    captchaProviderForm.value.fallbackProviders = normalizedChains.fallbackProviders;
    selectedCustomProviderId.value = customProviders[0]?.id || '';
};

const getProviderLabel = (providerName) => {
    return (
        providerLabelMap.value[providerName] ||
        getCaptchaProviderLabel(providerName, {
            customProviders: captchaProviderForm.value.customProviders,
        })
    );
};

const getCustomProviderMetaText = (provider) => {
    const providerId = createCustomProviderId(provider.id);
    return isCaptchaProviderAvailable(providerId, {
        customProviders: captchaProviderForm.value.customProviders,
    })
        ? '配置已完成，可加入链路'
        : '未完成配置，需补全接口地址与返回字段路径';
};

const getProviderChainType = (providerName) => {
    if (captchaProviderForm.value.providerPriority.includes(providerName)) {
        return 'priority';
    }
    if (captchaProviderForm.value.fallbackProviders.includes(providerName)) {
        return 'fallback';
    }
    return '';
};

const formatChainSummary = (providerNames) => {
    if (!providerNames?.length) {
        return '未配置';
    }
    return providerNames.map(getProviderLabel).join(' -> ');
};

const getProviderStatusText = (providerName) => {
    return getCaptchaProviderStatusText(providerName, {
        providerPriority: captchaProviderForm.value.providerPriority,
        fallbackProviders: captchaProviderForm.value.fallbackProviders,
        isAvailable: isCaptchaProviderAvailable(providerName, {
            customProviders: captchaProviderForm.value.customProviders,
        }),
    });
};

const selectCustomProvider = (providerId) => {
    selectedCustomProviderId.value = providerId;
};

const handleAddCustomProvider = () => {
    const provider = createEmptyCustomProvider();
    captchaProviderForm.value.customProviders.push(provider);
    selectedCustomProviderId.value = provider.id;
};

const removeCustomProvider = (providerId) => {
    const providerChainId = createCustomProviderId(providerId);
    captchaProviderForm.value.customProviders = captchaProviderForm.value.customProviders.filter(
        (provider) => provider.id !== providerId
    );
    captchaProviderForm.value.providerPriority = captchaProviderForm.value.providerPriority.filter(
        (provider) => provider !== providerChainId
    );
    captchaProviderForm.value.fallbackProviders = captchaProviderForm.value.fallbackProviders.filter(
        (provider) => provider !== providerChainId
    );
    if (selectedCustomProviderId.value === providerId) {
        selectedCustomProviderId.value = captchaProviderForm.value.customProviders[0]?.id || '';
    }
};

const assignProviderToChain = (providerName, chainType) => {
    if (
        !isCaptchaProviderAvailable(providerName, {
            customProviders: captchaProviderForm.value.customProviders,
        })
    ) {
        setCaptchaProviderNotice('请先完善自定义服务配置，再加入链路。', 'error');
        return;
    }
    const priority = captchaProviderForm.value.providerPriority.filter((name) => name !== providerName);
    const fallback = captchaProviderForm.value.fallbackProviders.filter((name) => name !== providerName);
    if (chainType === 'priority') {
        priority.push(providerName);
    } else {
        fallback.push(providerName);
    }
    const normalized = normalizeChainState(priority, fallback);
    captchaProviderForm.value.providerPriority = normalized.providerPriority;
    captchaProviderForm.value.fallbackProviders = normalized.fallbackProviders;
};

const canMoveProvider = (providerName, direction) => {
    const chainType = getProviderChainType(providerName);
    if (!chainType) {
        return false;
    }
    const list =
        chainType === 'priority'
            ? captchaProviderForm.value.providerPriority
            : captchaProviderForm.value.fallbackProviders;
    const index = list.indexOf(providerName);
    const nextIndex = index + direction;
    return nextIndex >= 0 && nextIndex < list.length;
};

const moveProvider = (providerName, direction) => {
    if (!canMoveProvider(providerName, direction)) {
        return;
    }
    const chainType = getProviderChainType(providerName);
    const list = [
        ...(chainType === 'priority'
            ? captchaProviderForm.value.providerPriority
            : captchaProviderForm.value.fallbackProviders),
    ];
    const index = list.indexOf(providerName);
    const nextIndex = index + direction;
    [list[index], list[nextIndex]] = [list[nextIndex], list[index]];
    if (chainType === 'priority') {
        captchaProviderForm.value.providerPriority = list;
    } else {
        captchaProviderForm.value.fallbackProviders = list;
    }
};

const removeProviderFromChain = (providerName) => {
    const normalized = normalizeChainState(
        captchaProviderForm.value.providerPriority.filter((name) => name !== providerName),
        captchaProviderForm.value.fallbackProviders.filter((name) => name !== providerName)
    );
    captchaProviderForm.value.providerPriority = normalized.providerPriority;
    captchaProviderForm.value.fallbackProviders = normalized.fallbackProviders;
};

const handleResetProviderStrategy = () => {
    const strategy = getDefaultCaptchaProviderStrategy();
    captchaProviderForm.value.providerPriority = [...strategy.providerPriority];
    captchaProviderForm.value.fallbackProviders = [...strategy.fallbackProviders];
    setCaptchaProviderNotice('回退链已恢复默认。');
};

const parseJsonObject = (text, providerName, fieldLabel) => {
    const source = text?.trim() || '{}';
    try {
        const parsed = JSON.parse(source);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
            throw new Error('JSON 必须是对象');
        }
        return parsed;
    } catch {
        throw new Error(`${providerName} 的${fieldLabel} JSON 格式不正确`);
    }
};

const buildCustomProvidersForSave = () => {
    return captchaProviderForm.value.customProviders.reduce((result, provider) => {
        const providerName = provider.name?.trim() || '未命名服务';
        const endpoint = provider.endpoint?.trim() || '';
        const resultPath = provider.resultPath?.trim() || '';
        const successPath = provider.successPath?.trim() || '';
        const successEquals = provider.successEquals?.trim() || '';
        const headersText = provider.headersJson?.trim() || '{}';
        const payloadText = provider.payloadJson?.trim() || '{}';
        const hasExtraConfig =
            Boolean(endpoint) ||
            Boolean(resultPath) ||
            Boolean(successPath) ||
            Boolean(successEquals) ||
            headersText !== '{}' ||
            payloadText !== '{}';

        if (!hasExtraConfig) {
            return result;
        }

        if (!endpoint || !resultPath) {
            throw new Error(`请先完善“${providerName}”的接口地址和返回字段路径`);
        }

        const headers = parseJsonObject(headersText, providerName, '请求头');
        const payload = parseJsonObject(payloadText, providerName, '额外参数');
        const method = provider.method === 'POST' ? 'POST' : 'GET';
        const normalizedProvider = {
            id: provider.id,
            name: providerName,
            endpoint,
            method,
            imageField: provider.imageField?.trim() || 'img',
            resultPath,
            headers,
            successPath,
        };
        if (successEquals !== '') {
            normalizedProvider.successEquals = successEquals;
        }
        if (method === 'GET') {
            normalizedProvider.query = payload;
        } else {
            normalizedProvider.body = payload;
        }
        result.push(normalizedProvider);
        return result;
    }, []);
};

const ensureOriginPermission = async (endpoint) => {
    const originPattern = `${new URL(endpoint).origin}/*`;
    const granted = await new Promise((resolve) => {
        chrome.permissions.contains({ origins: [originPattern] }, (state) => {
            resolve(Boolean(state));
        });
    });
    if (granted) {
        return;
    }
    const requested = await new Promise((resolve) => {
        chrome.permissions.request({ origins: [originPattern] }, (state) => {
            resolve(Boolean(state));
        });
    });
    if (!requested) {
        throw new Error(`未授予接口域名权限：${new URL(endpoint).origin}`);
    }
};

const ensurePermissionsForProviders = async (customProviders) => {
    const visitedOrigins = new Set();
    for (const provider of customProviders) {
        if (!provider.endpoint) {
            continue;
        }
        const origin = new URL(provider.endpoint).origin;
        if (visitedOrigins.has(origin)) {
            continue;
        }
        visitedOrigins.add(origin);
        await ensureOriginPermission(provider.endpoint);
    }
};

const buildRuntimeCaptchaConfig = async ({ requestPermissions = false } = {}) => {
    const customProviders = buildCustomProvidersForSave();
    const normalizedChains = normalizeChainState(
        captchaProviderForm.value.providerPriority,
        captchaProviderForm.value.fallbackProviders
    );
    const unavailableProviders = [...normalizedChains.providerPriority, ...normalizedChains.fallbackProviders]
        .filter((providerId) => providerId !== CAPTCHA_DEFAULT_PROVIDER)
        .filter(
            (providerId) =>
                !isCaptchaProviderAvailable(providerId, {
                    customProviders,
                })
        );

    if (unavailableProviders.length) {
        throw new Error(
            `请先完善 ${unavailableProviders.map(getProviderLabel).join('、')} 的配置后再加入链路`
        );
    }

    if (requestPermissions) {
        await ensurePermissionsForProviders(customProviders);
    }

    return buildCaptchaProviderStorageConfig({
        activeProvider: normalizedChains.providerPriority[0] || CAPTCHA_DEFAULT_PROVIDER,
        customProviders,
        providerPriority: normalizedChains.providerPriority,
        fallbackProviders: normalizedChains.fallbackProviders,
    });
};

const handleSaveCaptchaProvider = async () => {
    captchaProviderSaving.value = true;
    setCaptchaProviderNotice('', 'info');
    try {
        const config = await buildRuntimeCaptchaConfig({ requestPermissions: true });
        await setStorageValue(EXTENSION_STORAGE_KEYS.CAPTCHA_PROVIDER_CONFIG, config);
        applyFormConfig(config);
        setCaptchaProviderNotice('识别配置已保存。');
    } catch (error) {
        setCaptchaProviderNotice(error?.message || '保存失败，请检查配置', 'error');
    } finally {
        captchaProviderSaving.value = false;
    }
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

const handleExportCaptchaProviderConfig = async () => {
    try {
        const config = await buildRuntimeCaptchaConfig();
        const fileName = `xdu-captcha-provider-config-${new Date().toISOString().slice(0, 10)}.json`;
        downloadJsonFile(fileName, config);
        setCaptchaProviderNotice('识别配置已导出。');
    } catch (error) {
        setCaptchaProviderNotice(error?.message || '导出失败', 'error');
    }
};

const triggerCaptchaProviderImport = () => {
    captchaConfigImportInput.value?.click();
};

const handleImportCaptchaProviderConfig = async (event) => {
    const file = event?.target?.files?.[0];
    if (!file) {
        return;
    }
    try {
        const text = await file.text();
        const parsed = JSON.parse(text);
        const normalized = normalizeStoredCaptchaProviderConfig(parsed);
        await ensurePermissionsForProviders(normalized.customProviders);
        await setStorageValue(EXTENSION_STORAGE_KEYS.CAPTCHA_PROVIDER_CONFIG, normalized);
        applyFormConfig(normalized);
        setCaptchaProviderNotice('识别配置已导入。');
    } catch (error) {
        setCaptchaProviderNotice(error?.message || '导入失败', 'error');
    } finally {
        if (event?.target) {
            event.target.value = '';
        }
    }
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

const runBridgeTask = async (taskType, data = {}) => {
    const requestId = createRequestId();
    try {
        const raw = await props.bridge.sendToMain(taskType, data);
        return normalizeBridgeResponse(raw, requestId);
    } catch (error) {
        return createErrorResponse({
            requestId,
            code: ERROR_CODES.MESSAGE_SEND_FAILED,
            message: error?.message || '通信失败',
        });
    }
};

const fillDefaultTestImageUrl = () => {
    if (props.defaultTestImageUrl) {
        captchaTestImageUrl.value = props.defaultTestImageUrl;
    }
};

const handleRunCaptchaTest = async () => {
    if (!captchaTestImageUrl.value) {
        setCaptchaProviderNotice('请先输入验证码图片 URL', 'error');
        return;
    }
    captchaTestRunning.value = true;
    captchaTestResult.value = null;
    setCaptchaProviderNotice('', 'info');
    try {
        const runtimeConfig = await buildRuntimeCaptchaConfig({ requestPermissions: true });
        const chain = [...runtimeConfig.providerPriority, ...runtimeConfig.fallbackProviders];
        const response = await runBridgeTask(TASK_TYPES.CAPTCHA_TEST, {
            imageUrl: captchaTestImageUrl.value,
            provider: chain,
            customConfig: {
                customProviders: runtimeConfig.customProviders,
            },
        });
        if (!response.ok) {
            captchaTestResult.value = {
                success: false,
                attempts: response.error?.details?.attempts || [],
                errorMessage: response.error?.message || '测试失败',
                provider: '',
            };
            return;
        }
        const payload = response.data?.data || {};
        captchaTestResult.value = {
            success: true,
            provider: payload.provider || '',
            captcha: payload.captcha || '',
            attempts: payload.attempts || [],
            errorMessage: '',
        };
    } catch (error) {
        captchaTestResult.value = {
            success: false,
            attempts: [],
            errorMessage: error?.message || '测试失败',
            provider: '',
        };
    } finally {
        captchaTestRunning.value = false;
    }
};

onMounted(async () => {
    try {
        const raw = await getStorageValue(EXTENSION_STORAGE_KEYS.CAPTCHA_PROVIDER_CONFIG);
        applyFormConfig(raw);
    } catch {
        applyFormConfig(null);
        setCaptchaProviderNotice('加载识别配置失败', 'error');
    }
});
</script>
