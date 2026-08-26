export function getByPath(source, path) {
    if (!path || typeof path !== 'string') {
        return undefined;
    }

    const segments = path
        .split('.')
        .map((segment) => segment.trim())
        .filter(Boolean);
    if (segments.length === 0) {
        return undefined;
    }

    return segments.reduce((current, key) => {
        if (current == null || typeof current !== 'object') {
            return undefined;
        }
        return current[key];
    }, source);
}
