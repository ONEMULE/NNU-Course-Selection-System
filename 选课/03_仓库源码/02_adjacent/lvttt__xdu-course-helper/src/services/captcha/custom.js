import { getByPath } from './path-util.js';

function withImageField(input, imageField, imageUrl) {
    const result = { ...input };
    result[imageField] = imageUrl;
    return result;
}

function asObject(value) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
        return value;
    }
    return {};
}

export async function recognizeWithCustomProvider({ imageUrl, config, signal }) {
    const endpoint = config?.endpoint;
    const resultPath = config?.resultPath;
    if (!endpoint || !resultPath) {
        throw new Error('Custom captcha provider config is invalid');
    }

    const method = String(config?.method || 'GET').toUpperCase();
    const imageField = config?.imageField || 'img';
    const headers = asObject(config?.headers);
    const requestInit = {
        method,
        headers: { ...headers },
        signal,
    };

    let requestUrl = endpoint;
    if (method === 'GET') {
        const params = new URLSearchParams();
        const query = withImageField(asObject(config?.query), imageField, imageUrl);
        Object.entries(query).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
                params.set(key, String(value));
            }
        });
        const queryString = params.toString();
        if (queryString) {
            requestUrl = `${endpoint}${endpoint.includes('?') ? '&' : '?'}${queryString}`;
        }
    } else {
        if (!requestInit.headers['Content-Type']) {
            requestInit.headers['Content-Type'] = 'application/json';
        }
        const body = withImageField(asObject(config?.body), imageField, imageUrl);
        requestInit.body = JSON.stringify(body);
    }

    const response = await fetch(requestUrl, requestInit);
    if (!response.ok) {
        throw new Error(`Custom captcha provider request failed: HTTP ${response.status}`);
    }

    const payload = await response.json();
    if (config?.successPath) {
        const successValue = getByPath(payload, config.successPath);
        if (config.successEquals !== undefined) {
            if (String(successValue) !== String(config.successEquals)) {
                throw new Error('Custom captcha provider returned unsuccessful response');
            }
        } else if (!successValue) {
            throw new Error('Custom captcha provider returned unsuccessful response');
        }
    }

    const text = getByPath(payload, resultPath);
    if (typeof text !== 'string' || !text.trim()) {
        throw new Error('Custom captcha provider result path is invalid');
    }

    return text.trim();
}
