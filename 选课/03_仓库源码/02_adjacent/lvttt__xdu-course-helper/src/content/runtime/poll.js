export function poll(fn, maxAttempts = 10, interval = 200) {
    return new Promise((resolve, reject) => {
        let attempts = 0;

        const execute = () => {
            const result = fn();
            if (result) {
                resolve(result);
                return;
            }

            attempts += 1;
            if (attempts >= maxAttempts) {
                reject(new Error('Reached maximum attempts without success.'));
                return;
            }

            setTimeout(execute, interval);
        };

        execute();
    });
}
