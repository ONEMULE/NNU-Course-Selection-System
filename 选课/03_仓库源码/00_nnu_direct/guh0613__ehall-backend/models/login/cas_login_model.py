from typing import Optional

from fastapi.responses import JSONResponse
from pydantic import BaseModel


class CasLoginRequest(BaseModel):
    username: str
    password: str


class CasLoginResponse(BaseModel):
    status: str = "OK"
    message: str = "Login successful"
    authToken: Optional[str] = None

    @classmethod
    def create_response(cls, status_code: int = 200, **data) -> JSONResponse:
        instance = cls(**data)
        return JSONResponse(content=instance.model_dump(), status_code=status_code)
