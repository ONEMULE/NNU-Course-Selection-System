import re

from fastapi.responses import JSONResponse

from models.error.error_model import InternalErrorResponse, ErrorResponse
from models.login.cas_login_model import CasLoginResponse
from utils import cas_cache_utils
from utils.request_utils import general_cas_login


async def cas_authenticate(username: str, password: str) -> JSONResponse:
    submit_response = await general_cas_login(username, password)
    # response object will be requests.Response() if the login failed
    if submit_response.status_code != 200:
        return ErrorResponse.create_response(message="Failed to login. Please check your username and password.")

    # if success, the response will have a location header, follow the redirect and get the ticket and castgc
    # check if the request was redirected
    if submit_response.history:
        for resp in submit_response.history:
            location = resp.headers.get('Location')
            ticket = re.search(r'ticket=([^&#]+)', location).group(1)
            castgc = resp.cookies.get('CASTGC')
            # mod_auth_cas is the specific cookie for nnu
            mod_auth_cas = "MOD_AUTH_" + ticket
            cas_cache_utils.set_mod_auth_cas(castgc, mod_auth_cas)
            return CasLoginResponse.create_response(authToken=castgc)
    else:
        return InternalErrorResponse.create_response()

    return InternalErrorResponse.create_response()
