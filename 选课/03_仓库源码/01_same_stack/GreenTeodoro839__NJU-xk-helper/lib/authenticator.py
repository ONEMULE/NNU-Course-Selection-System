"""
认证器：执行完整的登录流程（验证码获取→识别→提交登录）。

原 xklogin.py，重命名以区分职责：
  - authenticator.py: 执行登录流程
  - session_manager.py: 管理登录态生命周期（缓存/验证/刷新）

对外接口: perform_login(conf_path=None) -> (cookies_dict, token) or (None, None)
"""

import json
import os
import time

import requests

from lib.captcha import solve_captcha_from_base64
from lib.common import CONF_DIR, USER_AGENT, load_xk_config, build_proxies
from lib.des_encrypt import encrypt_password
from lib.serverchan import send_serverchan_notification

BASE_URL = "https://xk.nju.edu.cn/xsxkapp/sys/xsxkapp"
INDEX_URL = f"{BASE_URL}/*default/index.do"
VCODE_API = f"{BASE_URL}/student/4/vcode.do"
LOGIN_API = f"{BASE_URL}/student/check/login.do"


def perform_login() -> tuple:
    """执行完整登录流程。

    从 config/xk.conf 读取账号密码等配置，完成登录后返回 (cookies_dict, token)。
    失败返回 (None, None)。
    """
    conf = load_xk_config()
    username = conf.get("USER")
    max_retries = int(conf.get("MAX_RETRIES", 3))

    # 密码：优先明文实时加密，兼容旧的加密文本
    raw_pwd = conf.get("PWD")
    password = encrypt_password(raw_pwd) if raw_pwd else conf.get("PWD_ENCRYPT")

    if not username or not password:
        raise ValueError("配置文件中缺少 USER 或 PWD")

    # 代理
    proxy_url = (conf.get("PROXY") or "").strip() or None
    proxies = build_proxies(proxy_url)
    if proxies:
        print(f">>> 启用代理: {proxy_url}")
    else:
        print(">>> 未配置代理，使用直连模式")

    def _new_session():
        s = requests.Session()
        s.trust_env = False
        s.headers.update({
            "User-Agent": USER_AGENT,
            "Referer": INDEX_URL,
            "Origin": "https://xk.nju.edu.cn",
            "X-Requested-With": "XMLHttpRequest"
        })
        if proxies:
            s.proxies = proxies
        return s

    session = _new_session()

    for attempt in range(max_retries):
        try:
            print(f"\n====== 尝试第 {attempt + 1}/{max_retries} 次登录 ======")

            # Step 1: 初始化 Session
            print(">>> 1. 初始化 Session...")
            session.get(INDEX_URL, timeout=10)

            # Step 2: 获取验证码
            print(">>> 2. 获取验证码...")
            vcode_resp = session.post(VCODE_API, timeout=10)
            vcode_json = vcode_resp.json()

            data_node = vcode_json.get("data", {})
            server_uuid = data_node.get("uuid")
            img_b64_raw = data_node.get("vode") or data_node.get("vcode")

            if not server_uuid or not img_b64_raw:
                print(f"❌ 响应数据不完整: {vcode_json}")
                continue

            img_gif_b64_body = img_b64_raw.split(",")[1] if "," in img_b64_raw else img_b64_raw

            # Step 3: 识别验证码
            print(">>> 3. 识别验证码...")
            points = solve_captcha_from_base64(img_gif_b64_body)
            if not points:
                print("❌ 识别失败")
                continue

            coord_str_list = [f"{int(p[0])}-{int(p[1] * 5 / 6)}" for p in points]
            verify_code = ",".join(coord_str_list)
            print(f"    提交坐标: {verify_code}")

            # Step 4: 发送登录请求
            payload = {
                "loginName": username,
                "loginPwd": password,
                "verifyCode": verify_code,
                "vtoken": "",
                "uuid": server_uuid,
            }

            print(">>> 4. 发送登录请求...")
            login_resp = session.post(LOGIN_API, data=payload, timeout=15)
            login_json = login_resp.json()

            # Step 5: 结果校验
            resp_code = login_json.get("code")
            resp_data = login_json.get("data") or {}

            if str(resp_code) == "1" and str(resp_data.get("number")) == str(username):
                token = resp_data.get("token")
                print(f"✅ 登录成功!")
                return session.cookies.get_dict(), token
            else:
                msg = login_json.get("msg", "未知错误")
                print(f"❌ 登录失败: {msg} (Code: {resp_code})")

                # 服务端拒绝当前会话时重建 Session
                if str(resp_code).startswith("#E"):
                    print("⚠️  服务端拒绝当前会话，正在重建 Session...")
                    session.close()
                    session = _new_session()

        except Exception as e:
            print(f"❌ 异常: {e}")
            time.sleep(1)

    send_serverchan_notification("❌ 登录失败", "🚫 登录失败，已达最大重试次数。")
    print("🚫 登录失败，已达最大重试次数。")
    return None, None


if __name__ == "__main__":
    c, t = perform_login()
    if t:
        print("Final Token:", t)
