import { testCaptchaProviderChain } from '../../services/captcha/index.js';

export async function handleCaptchaTest(tabId, data = {}) {
    const { imageUrl, provider, customConfig, timeoutMs } = data;
    const result = await testCaptchaProviderChain({
        imageUrl,
        provider,
        customConfig,
        timeoutMs,
    });

    return {
        code: '1',
        msg: '验证码测试完成',
        data: result,
    };
}
