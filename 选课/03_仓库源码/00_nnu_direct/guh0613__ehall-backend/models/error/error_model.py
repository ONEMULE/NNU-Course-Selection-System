from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str = "Something went wrong."

    @classmethod
    def create_response(cls, status_code: int = 400, **data) -> JSONResponse:
        instance = cls(**data)
        return JSONResponse(content=instance.model_dump(), status_code=status_code)


class ExpireErrorResponse(BaseModel):
    status: str = "error"
    message: str = "AuthToken expired. Please re-login."

    @classmethod
    def create_response(cls, status_code: int = 401, **data) -> JSONResponse:
        instance = cls(**data)
        return JSONResponse(content=instance.model_dump(), status_code=status_code)


class InternalErrorResponse(BaseModel):
    status: str = "retry"
    message: str = "Internal error. Please try again later."

    @classmethod
    def create_response(cls, status_code: int = 402, **data) -> JSONResponse:
        instance = cls(**data)
        return JSONResponse(content=instance.model_dump(), status_code=status_code)
