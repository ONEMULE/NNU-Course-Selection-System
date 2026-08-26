import re

import httpx
from cachetools import TTLCache

from utils.common_utils import get_cas_url
from utils.request_utils import get_auth_headers

cache = TTLCache(maxsize=1024, ttl=2400)


async def refresh_mod_auth_cas(castgc):
    cas_url = get_cas_url()
    async with httpx.AsyncClient() as s:
        s.headers.update(get_auth_headers())
        s.cookies.set('CASTGC', castgc)
        auth_response = await s.get(cas_url)
        if auth_response.history:
            for resp in auth_response.history:
                location = resp.headers.get('Location')
                ticket = re.search(r'ticket=([^&#]+)', location).group(1)
                mod_auth_cas = "MOD_AUTH_" + ticket
                return mod_auth_cas
        else:
            return None
        return None


async def get_mod_auth_cas(castgc):
    mod_auth_cas = cache.get(castgc)
    if mod_auth_cas is None:
        mod_auth_cas = await refresh_mod_auth_cas(castgc)
        if mod_auth_cas is None:
            return None
        cache[castgc] = mod_auth_cas
    return mod_auth_cas


def set_mod_auth_cas(castgc, mod_auth_cas):
    cache[castgc] = mod_auth_cas
    return True
