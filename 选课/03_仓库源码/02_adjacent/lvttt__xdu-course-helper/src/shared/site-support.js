export function isSupportedCourseUrl(url) {
    return typeof url === 'string' && url.includes('https://yjsxk.xidian.edu.cn/yjsxkapp/sys/xsxkapp/');
}
