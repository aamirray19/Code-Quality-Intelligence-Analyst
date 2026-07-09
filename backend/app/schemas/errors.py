from pydantic import BaseModel


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
