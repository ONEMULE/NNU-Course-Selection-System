from fastapi import APIRouter

from handlers.login_handler import cas_login_handler
from models.login.cas_login_model import CasLoginRequest

router = APIRouter()


@router.post('/cas_login')
async def cas_login(login_data: CasLoginRequest):
    return await cas_login_handler(login_data)
