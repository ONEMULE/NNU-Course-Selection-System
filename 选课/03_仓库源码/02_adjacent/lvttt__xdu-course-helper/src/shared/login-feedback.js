export function createMissingSavedLoginResponse() {
    return {
        type: 'error',
        msg: '需要先开启“记住账号密码”，并成功登录一次后，才能使用此功能。',
    };
}

export function getLoginResponseClass(response) {
    return response?.type === 'error'
        ? 'bg-red-50 border border-red-100 text-red-700'
        : 'bg-blue-50 border border-blue-100 text-blue-800';
}
