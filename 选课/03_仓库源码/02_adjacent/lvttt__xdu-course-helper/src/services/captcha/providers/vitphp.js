export async function recognizeWithVitphp({ imageUrl, signal }) {
    const endpoint = `https://api.vitphp.cn/Yzcode/?img=${encodeURIComponent(imageUrl)}`;
    const response = await fetch(endpoint, {
        method: 'GET',
        signal,
    });

    if (!response.ok) {
        throw new Error(`Captcha provider request failed: HTTP ${response.status}`);
    }

    const payload = await response.json();
    if (payload?.code !== 1 || typeof payload?.captcha !== 'string') {
        throw new Error(payload?.message || 'Captcha provider returned invalid response');
    }

    return payload.captcha.trim();
}
