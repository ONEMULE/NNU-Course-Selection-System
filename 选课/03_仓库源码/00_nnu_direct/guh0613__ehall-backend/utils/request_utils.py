import re
from datetime import datetime
from typing import Optional

import httpx

from utils.common_utils import get_cas_url
from utils.encryption_utils import aes_cbc_encrypt_url, random_string

default_header = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": "\"Chromium\";v=\"119\", \"Not?A_Brand\";v=\"24\"",
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": "\"macOS\"",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Priority": "u=0, i",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.90 Safari/537.36"
}


def get_auth_headers() -> dict:
    """return the auth submit headers for the specified school."""
    header = default_header
    header["Referer"] = ("https://authserver.nnu.edu.cn/authserver/login?service=https%3A%2F%2Fehall.nnu.edu.cn"
                         "%2Flogin%3Fservice%3Dhttp%3A%2F%2Fehall.nnu.edu.cn%2Fywtb-portal%2Fstandard%2Findex.html%23"
                         "%2FWorkBench%2Fworkbench")
    return header


def get_timestamp() -> str:
    """return the current timestamp"""
    return str(int(datetime.now().timestamp() * 1000))


async def general_cas_login(username: str, password: str) -> Optional[httpx.Response]:
    """General CAS login function."""
    cas_url = get_cas_url()

    async with httpx.AsyncClient(follow_redirects=True) as client:
        client.headers.update(get_auth_headers())

        auth_response = await client.get(cas_url)

        pattern = (r'<input type="hidden" id="pwdEncryptSalt" value="(.+?)" /><input type="hidden" id="execution" '
                   r'name="execution" value="(.+?)" />')
        match = re.search(pattern, auth_response.text)
        if match is None:
            # return None to indicate failure
            return None

        salt = match.group(1)
        execution = match.group(2)

        encrypted_password = aes_cbc_encrypt_url((random_string(64) + password).encode(), salt.encode())
        submit_data = {
            'username': username,
            'password': encrypted_password.decode(),
            'captcha': '',
            '_eventId': 'submit',
            'cllt': 'userNameLogin',
            'dllt': 'generalLogin',
            'lt': '',
            'execution': execution,
        }

        submit_response = await client.post(cas_url, data=submit_data, headers=get_auth_headers())
        return submit_response
