import { recognizeCaptchaImage } from '../../services/captcha/index.js';

export async function handleCaptchaRecognize(tabId, data = {}) {
    const { imageUrl, provider, customConfig, timeoutMs } = data;
    const result = await recognizeCaptchaImage({
        imageUrl,
        provider,
        customConfig,
        timeoutMs,
    });

    return {
        code: '1',
        msg: '验证码识别成功',
        data: result,
    };
}
