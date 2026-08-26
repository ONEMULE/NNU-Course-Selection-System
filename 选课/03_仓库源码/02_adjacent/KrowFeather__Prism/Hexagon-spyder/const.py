VCODE_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.8",
    "Connection": "keep-alive",
    "Host": "xk.ynu.edu.cn",
    "Referer": "http://xk.ynu.edu.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "X-Requested-With": "XMLHttpRequest"
}

LOGIN_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "Connection": "keep-alive",
    "Host": "xk.ynu.edu.cn",
    "Priority": "u=0",
    "Referer": "https://xk.ynu.edu.cn/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "X-Requested-With": "XMLHttpRequest"
}

REC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "token": "",
    "X-Requested-With": "XMLHttpRequest",
    "Priority": "u=0",
    "Origin": "https://xk.ynu.edu.cn",
    "Host": "xk.ynu.edu.cn"
}

VCODE_URL = "https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/student/4/vcode.do?timestamp={timestamp}"
CAPTCHA_URL = "https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/student/vcode/image.do?vtoken={token}"
LOGIN_URL = "https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/student/check/login.do?timestrap={timestamp}&loginName={username}&loginPwd={password}&verifyCode={code}&vtoken={token}"
REC_URL = "https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/elective/recommendedCourse.do"
SYS_PARAM_URL = "https://xk.ynu.edu.cn/xsxkapp/sys/xsxkapp/publicinfo/sysparam.do"