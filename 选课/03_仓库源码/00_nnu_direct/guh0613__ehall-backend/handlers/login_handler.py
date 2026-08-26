from models.login.cas_login_model import CasLoginRequest
from services.cas_auth_service import cas_authenticate


async def cas_login_handler(login_data: CasLoginRequest):
    return await cas_authenticate(login_data.username, login_data.password)
