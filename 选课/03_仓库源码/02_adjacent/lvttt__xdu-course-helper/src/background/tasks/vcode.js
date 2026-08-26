// src/background/tasks/vcode.js

export function createVcodeImageUrl(vcodeToken) {
    return `https://yjsxk.xidian.edu.cn/yjsxkapp/sys/xsxkapp/login/vcode/image.do?vtoken=${vcodeToken}`;
}

// 获取验证码token
export async function getVcodeToken(tabId) {
    return chrome.scripting
        .executeScript({
            target: { tabId },
            world: 'MAIN',
            func: async () => {
                const vcode_url =
                    'https://yjsxk.xidian.edu.cn/yjsxkapp/sys/xsxkapp/login/4/vcode.do';
                // 清除Cookie中的_WEU
                document.cookie =
                    '_WEU=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=' +
                    commonUtil.getProjectName();

                return await fetch(vcode_url)
                    .then((response) => response.json())
                    .then((data) => {
                        console.log('获取验证码token成功:', data);
                        return data.data.token;
                    })
                    .catch((err) => {
                        console.error('获取验证码token失败:', err);
                        throw err;
                    });
            },
        })
        .then((results) => {
            const [{ result }] = results;
            return result;
        });
}
